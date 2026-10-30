import hashlib
import importlib.util
from pathlib import Path
import tarfile
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'repository_signing', Path(__file__).resolve().parents[1] / 'scripts/sign-repository.py')
signing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signing)


class MetadataSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def fixture(self, name):
        site = self.root / name
        repo = site / '44/testing/aarch64'
        data = repo / 'repodata'
        data.mkdir(parents=True)
        (site / 'RPM-GPG-KEY-aurora').write_bytes(b'public key')
        (repo / 'manifest.json').write_bytes(b'{"packages": []}\n')
        content = b'compressed primary metadata'
        (data / 'primary.xml.gz').write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        (data / 'repomd.xml').write_text(
            '<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary">'
            f'<checksum type="sha256">{digest}</checksum>'
            '<location href="repodata/primary.xml.gz"/>'
            f'<size>{len(content)}</size></data></repomd>')
        (data / 'repomd.xml.asc').write_bytes(b'signature fixture')
        (repo / 'package-1.aarch64.rpm').write_bytes(b'package assets stay outside metadata snapshots')
        return site

    def test_archive_preserves_exact_metadata_and_excludes_package_copies(self):
        site = self.fixture('site')
        archive = signing.archive_metadata(site, 'testing-fixture.1')
        with tarfile.open(archive) as bundle:
            members = bundle.getmembers()
            self.assertEqual({entry.name for entry in members}, {
                'RPM-GPG-KEY-aurora', '44/testing/aarch64/manifest.json',
                '44/testing/aarch64/repodata/repomd.xml',
                '44/testing/aarch64/repodata/repomd.xml.asc',
                '44/testing/aarch64/repodata/primary.xml.gz',
            })
            for entry in members:
                self.assertTrue(entry.isfile())
                self.assertEqual(bundle.extractfile(entry).read(), (site / entry.name).read_bytes())
                self.assertEqual((entry.uid, entry.gid, entry.mtime, entry.mode), (0, 0, 0, 0o644))

    def test_metadata_archive_is_reproducible_and_never_overwritten(self):
        a, b = self.fixture('a'), self.fixture('b')
        first = signing.archive_metadata(a, 'testing-fixture.1')
        second = signing.archive_metadata(b, 'testing-fixture.1')
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with self.assertRaises(FileExistsError):
            signing.archive_metadata(a, 'testing-fixture.1')

    def test_missing_modified_linked_or_escaping_metadata_is_rejected(self):
        for index, failure in enumerate(['missing', 'modified', 'link', 'escape', 'missing-key']):
            with self.subTest(failure=failure):
                site = self.fixture(str(index))
                repodata = site / '44/testing/aarch64/repodata'
                primary = repodata / 'primary.xml.gz'
                if failure == 'missing':
                    primary.unlink()
                elif failure == 'modified':
                    primary.write_bytes(b'changed bytes')
                elif failure == 'link':
                    original = primary.read_bytes()
                    primary.unlink()
                    (self.root / 'outside').write_bytes(original)
                    primary.symlink_to(self.root / 'outside')
                elif failure == 'escape':
                    index_path = repodata / 'repomd.xml'
                    index_path.write_text(index_path.read_text().replace(
                        'repodata/primary.xml.gz', '../private-key'))
                else:
                    (site / 'RPM-GPG-KEY-aurora').unlink()
                with self.assertRaises(ValueError):
                    signing.archive_metadata(site, 'testing-fixture.1')
                self.assertFalse((site / 'repository-metadata-testing-fixture.1.tar.gz').exists())

    def test_snapshot_tag_cannot_escape_the_output_directory(self):
        site = self.fixture('site')
        for name in ['../snapshot', 'testing-../../secret', 'release-1', 'testing-1/extra']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                signing.archive_metadata(site, name)

    def test_signer_rejects_a_snapshot_named_for_another_release_before_signing(self):
        result = subprocess.run([
            sys.executable, str(Path(signing.__file__)), '--rpms', str(self.root),
            '--output', str(self.root / 'output'), '--snapshot', 'testing-fixture.1',
            '--asset-base', 'https://example.com/releases/testing-other',
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('snapshot tag does not match', result.stderr)
        self.assertFalse((self.root / 'output').exists())

    def test_packages_are_published_under_the_name_github_stores(self):
        # GitHub stored aura-1.0.0~b1-1.fc44.aarch64.rpm as aura-1.0.0.b1-...,
        # so testing-20261030.5's repository pointed at a missing asset.
        self.assertEqual(signing.asset_name('aura-1.0.0~b1-1.fc44.aarch64.rpm'),
                         'aura-1.0.0.b1-1.fc44.aarch64.rpm')
        for name in ['kernel-aurora-core-7.3.0-5.fc44.aurora.aarch64.rpm', 'mesa_x-1.0-1.noarch.rpm']:
            self.assertEqual(signing.asset_name(name), name)

    def test_signer_refuses_two_rpms_with_one_asset_name_before_signing(self):
        rpms = self.root / 'rpms'
        rpms.mkdir()
        for name in ['tool-1.0~b1-1.noarch.rpm', 'tool-1.0.b1-1.noarch.rpm']:
            (rpms / name).write_bytes(b'rpm')
        result = subprocess.run([
            sys.executable, str(Path(signing.__file__)), '--rpms', str(rpms),
            '--output', str(self.root / 'output'), '--snapshot', 'testing-fixture.1',
            '--asset-base', 'https://example.com/releases/testing-fixture.1',
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('share one release asset name', result.stderr)
        self.assertFalse((self.root / 'output').exists())


if __name__ == '__main__':
    unittest.main()
