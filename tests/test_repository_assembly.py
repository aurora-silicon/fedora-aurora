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
