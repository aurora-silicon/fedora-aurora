"""Publishing a small build delta must preserve the rest of the hardware stack."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('assembly', ROOT / 'scripts/assemble-repository.py')
assembly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembly)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / 'base'
        self.candidates = self.root / 'candidates'
        self.base.mkdir()
        self.candidates.mkdir()
        self.rows = {}
        self.addCleanup(patch.stopall)
        patch.object(assembly, 'metadata', side_effect=lambda p: self.rows[p.name]).start()

    def rpm(self, directory, filename, name, source):
        (directory / filename).write_text(filename)
        self.rows[filename] = (name, 'aarch64', source)

    def test_incremental_snapshot_keeps_mesa_and_retires_all_old_kernel_outputs(self):
        self.rpm(self.base, 'mesa.rpm', 'mesa-aurora', 'mesa-aurora-26.3-1.src.rpm')
        self.rpm(self.base, 'kernel-old.rpm', 'kernel-aurora-core', 'kernel-aurora-7.2.10-1.src.rpm')
        self.rpm(self.base, 'obsolete-old.rpm', 'kernel-obsolete', 'kernel-aurora-7.2.10-1.src.rpm')
        self.rpm(self.candidates, 'kernel-new.rpm', 'kernel-aurora-core', 'kernel-aurora-7.2.10-2.src.rpm')
        result = assembly.assemble(self.base, self.candidates, self.root / 'result',
                                   {'mesa-aurora-26.3-1.src.rpm', 'kernel-aurora-7.2.10-2.src.rpm'})
        self.assertEqual(result, ['kernel-new.rpm', 'mesa.rpm'])

    def test_nosource_recipe_is_never_put_in_the_binary_repository(self):
        source = 'tools-1-1.nosrc.rpm'
        self.rpm(self.candidates, 'tools.rpm', 'tools', source)
        (self.candidates / source).write_bytes(b'recipe only')
        result = assembly.assemble(None, self.candidates, self.root / 'result', {source})
        self.assertEqual(result, ['tools.rpm'])
        self.assertFalse((self.root / 'result' / source).exists())

    def test_partial_first_snapshot_is_rejected_before_writing(self):
        self.rpm(self.candidates, 'power.rpm', 'upower', 'upower-1.91.4-1.src.rpm')
        output = self.root / 'result'
        with self.assertRaisesRegex(ValueError, 'Incomplete or stale snapshot'):
            assembly.assemble(None, self.candidates, output, {'upower-1.91.4-1.src.rpm', 'kernel-aurora-7.2.10-2.src.rpm'})
        self.assertFalse(output.exists())

    def test_stale_base_kernel_cannot_satisfy_the_current_recipe(self):
        self.rpm(self.base, 'kernel-old.rpm', 'kernel-aurora-core', 'kernel-aurora-7.2.10-1.src.rpm')
        self.rpm(self.candidates, 'power.rpm', 'upower', 'upower-1.91.4-1.src.rpm')
        with self.assertRaisesRegex(ValueError, 'kernel-aurora-7.2.10-2'):
            assembly.assemble(self.base, self.candidates, self.root / 'result',
                              {'upower-1.91.4-1.src.rpm', 'kernel-aurora-7.2.10-2.src.rpm'})

    def test_removed_recipe_is_pruned_from_the_base_snapshot(self):
        self.rpm(self.base, 'retired.rpm', 'retired-package', 'retired-package-1-1.src.rpm')
        self.rpm(self.base, 'mesa.rpm', 'mesa-aurora', 'mesa-aurora-26.3-1.src.rpm')
        self.rpm(self.candidates, 'mesa-new.rpm', 'mesa-aurora', 'mesa-aurora-26.3-2.src.rpm')
        result = assembly.assemble(self.base, self.candidates, self.root / 'result',
                                   {'mesa-aurora-26.3-2.src.rpm'})
        self.assertEqual(result, ['mesa-new.rpm'])


class RequiredFirefoxTests(unittest.TestCase):
    """A snapshot carries Aurora's firefox and firefox-langpacks together, or fails."""
    SOURCE = 'firefox-160.0-1.fc44.aurora2.src.rpm'
    MESA = 'mesa-aurora-26.3-1.src.rpm'

    setUp = RepositoryTests.setUp

    def rpm(self, directory, filename, name, source, arch='aarch64'):
        (directory / filename).write_text(filename)
        self.rows[filename] = (name, arch, source)

    def assemble(self, expected=(SOURCE, MESA), base=None):
        self.rpm(self.candidates, 'mesa.rpm', 'mesa-aurora', self.MESA)
        return assembly.assemble(base, self.candidates, self.root / 'result', set(expected))

    def assert_refused(self, pattern, **kwargs):
        with self.assertRaisesRegex(ValueError, pattern) as caught:
            self.assemble(**kwargs)
        self.assertFalse((self.root / 'result').exists())
        return caught.exception

    def test_an_aurora_pair_is_published(self):
        self.rpm(self.candidates, 'firefox.rpm', 'firefox', self.SOURCE)
        self.rpm(self.candidates, 'langpacks.rpm', 'firefox-langpacks', self.SOURCE)
        self.assertEqual(self.assemble(), ['firefox.rpm', 'langpacks.rpm', 'mesa.rpm'])

    def test_a_pair_reused_from_the_base_snapshot_is_published(self):
        self.rpm(self.base, 'firefox.rpm', 'firefox', self.SOURCE)
        self.rpm(self.base, 'langpacks.rpm', 'firefox-langpacks', self.SOURCE)
        self.assertEqual(self.assemble(base=self.base), ['firefox.rpm', 'langpacks.rpm', 'mesa.rpm'])

    def test_omitting_either_package_fails(self):
        for present, absent in (('firefox', 'firefox-langpacks'), ('firefox-langpacks', 'firefox')):
            with self.subTest(absent=absent):
                for path in self.candidates.glob('*.rpm'):
                    path.unlink()
                self.rpm(self.candidates, 'present.rpm', present, self.SOURCE)
                error = self.assert_refused(f'Snapshot lacks {absent}.aarch64 from {self.SOURCE}')
                self.assertEqual(error.recipe, 'firefox')

    def test_omitting_both_fails_as_an_incomplete_snapshot(self):
        self.assert_refused('Incomplete or stale snapshot.*firefox-160.0-1.fc44.aurora2')

    def test_source_and_debuginfo_packages_do_not_count(self):
        self.rpm(self.candidates, 'langpacks.rpm', 'firefox-langpacks', self.SOURCE)
        self.rpm(self.candidates, 'debuginfo.rpm', 'firefox-debuginfo', self.SOURCE)
        (self.candidates / self.SOURCE).write_text('source')
        self.assert_refused('Snapshot lacks firefox.aarch64')

    def test_another_architecture_does_not_count(self):
        self.rpm(self.candidates, 'firefox.rpm', 'firefox', self.SOURCE, arch='noarch')
        self.rpm(self.candidates, 'langpacks.rpm', 'firefox-langpacks', self.SOURCE)
        self.assert_refused('Snapshot lacks firefox.aarch64')

    def test_a_stock_build_cannot_stand_in(self):
        stock = 'firefox-159.0.1-1.fc44.src.rpm'
        self.rpm(self.candidates, 'firefox.rpm', 'firefox', stock)
        self.rpm(self.candidates, 'langpacks.rpm', 'firefox-langpacks', self.SOURCE)
        self.assert_refused('Duplicate|Incomplete|comes from')
        # Nor as the recipe's expected source.
        for path in self.candidates.glob('*.rpm'):
            path.unlink()
        self.rpm(self.candidates, 'firefox.rpm', 'firefox', stock)
        self.rpm(self.candidates, 'langpacks.rpm', 'firefox-langpacks', stock)
        self.assert_refused(f'firefox: {stock} is not an Aurora build', expected=(stock, self.MESA))

    def test_mismatched_versions_fail(self):
        # A fresh firefox with the previous build's langpacks left in the base.
        self.rpm(self.base, 'langpacks-old.rpm', 'firefox-langpacks', 'firefox-159.0-1.fc44.aurora1.src.rpm')
        self.rpm(self.candidates, 'firefox.rpm', 'firefox', self.SOURCE)
        self.assert_refused('Snapshot lacks firefox-langpacks.aarch64', base=self.base)

    def test_a_release_without_the_recipe_is_not_affected(self):
        self.assertEqual(self.assemble(expected=(self.MESA,)), ['mesa.rpm'])


class BaseSnapshotNameTests(unittest.TestCase):
    """testing-20261030.5's manifest lists aura-1.0.0~b1-..., but GitHub
    stored and downloads that asset as aura-1.0.0.b1-...."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        patch.object(assembly, 'verify_signature').start()
        patch.object(assembly.subprocess, 'run').start()

    def snapshot(self, listed, stored):
        content = b'signed aura'
        (self.base / stored).write_bytes(content)
        (self.base / 'manifest.json').write_text(json.dumps({'signing_key': 'F' * 40, 'packages': [
            {'filename': listed, 'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}]}))

    def test_a_base_listing_a_tilde_name_matches_the_stored_asset(self):
        self.snapshot('aura-1.0.0~b1-1.fc44.aarch64.rpm', 'aura-1.0.0.b1-1.fc44.aarch64.rpm')
        assembly.verify_base(self.base, Path('key'), 'F' * 40)
        assembly.verify_signature.assert_called_once()

    def test_a_base_asset_under_another_name_is_still_refused(self):
        self.snapshot('aura-1.0.0~b1-1.fc44.aarch64.rpm', 'aura-1.0.0-1.fc44.aarch64.rpm')
        with self.assertRaisesRegex(ValueError, 'inventory differs'):
            assembly.verify_base(self.base, Path('key'), 'F' * 40)

    def test_signer_and_assembler_name_assets_alike(self):
        signing_spec = importlib.util.spec_from_file_location('signing', ROOT / 'scripts/sign-repository.py')
        signing = importlib.util.module_from_spec(signing_spec)
        signing_spec.loader.exec_module(signing)
        for name in ['aura-1.0.0~b1-1.fc44.aarch64.rpm', 'a+b-1-1.noarch.rpm', 'plain-1-1.noarch.rpm']:
            self.assertEqual(assembly.asset_name(name), signing.asset_name(name))


class SignatureTests(unittest.TestCase):
    def test_digest_only_success_is_not_an_authenticated_signature(self):
        with patch.object(assembly.subprocess, 'check_output', return_value='package.rpm: digests OK\n'):
            with self.assertRaisesRegex(ValueError, 'no authenticated signature'):
                assembly.verify_signature(Path('package.rpm'), Path('keydb'))

    def test_imported_key_signature_is_required_in_rpmkeys_output(self):
        output = '    Header OpenPGP V4 EdDSA/SHA512 signature, key fingerprint: abc: OK\n'
        with patch.object(assembly.subprocess, 'check_output', return_value=output):
            assembly.verify_signature(Path('package.rpm'), Path('keydb'))
