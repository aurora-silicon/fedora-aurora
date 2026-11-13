import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('carry_heavy_f45', ROOT / 'scripts/carry-heavy-f45.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
fedoralib = module.fedoralib

RPM = b'signed firefox payload\n'
LANGPACKS = b'signed langpacks payload\n'
BINARIES = {'firefox-160.0-1.fc45.aurora2.aarch64.rpm': RPM,
            'firefox-langpacks-160.0-1.fc45.aurora2.aarch64.rpm': LANGPACKS}


def row(filename, data):
    return {'filename': filename, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


class CarryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.root = self.temp / 'repo'
        for name, text in (('firefox', '# aurora-builder: heavy\nName: firefox\n'), ('mutter', 'Name: mutter\n')):
            recipe = self.root / 'packages' / name / f'{name}.spec'
            recipe.parent.mkdir(parents=True)
            recipe.write_text(text)
        (self.root / 'packages/firefox/f45').mkdir()
        (self.root / 'packages/firefox/f45/distgit.json').write_text('{"commit": "1"}\n')
        self.candidates = self.temp / 'candidates'
        self.built('mutter')
        self.output = self.temp / 'carried'
        self.assets = {}
        self.releases = []
        self.downloads = []
        old = self.receipt()
        self.snapshot('testing-f45-20261112.4', base='testing-f45-20261112.3', receipts=[old])
        self.snapshot('testing-f45-20261113.1', base='testing-f45-20261112.4', receipts=[])

    def built(self, name):
        receipt = self.candidates / f'rpm-f45-{name}/out/manifests/{name}.json'
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps({'package': name, 'fedora': 45}))

    def receipt(self, inputs=None):
        artifacts = [row(name, b'unsigned ' + data) for name, data in BINARIES.items()]
        artifacts.append(row('firefox-160.0-1.fc45.aurora2.src.rpm', b'source'))
        return {'schema': 1, 'package': 'firefox', 'fedora': 45, 'succeeded': True, 'architecture': 'aarch64',
                'recipe_inputs': inputs or fedoralib.recipe_inputs(self.root, 'firefox', 45),
                'artifacts': artifacts}

    def snapshot(self, tag, base, receipts, files=BINARIES, fedora=45):
        manifest = {'schema': 1, 'fedora': fedora, 'dry_run': False, 'signing_key': 'F' * 40,
                    'packages': [row('mutter-50.1-1.fc45.aurora1.aarch64.rpm', b'mutter')]
                    + [row(name, data) for name, data in files.items()]}
        self.assets[tag] = {'manifest.json': json.dumps(manifest).encode(),
                            'builds.json': json.dumps({'base_release': base, 'receipts': receipts}).encode(),
                            'mutter-50.1-1.fc45.aurora1.aarch64.rpm': b'mutter', **files}
        self.releases.append({'id': len(self.releases) + 1, 'tag_name': tag, 'draft': False,
                              'created_at': f'2026-11-{len(self.releases) + 10:02d}T00:00:00Z',
                              'assets': [{'name': name} for name in self.assets[tag]]})

    def download(self, tag, name, directory):
        self.downloads.append((tag, name))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes(self.assets[tag][name])
        return directory / name

    def read_json(self, tag, name):
        return json.loads(self.assets[tag][name])

    def carry(self):
        return module.carry(self.root, self.candidates, self.output, self.releases, self.read_json, self.download)

    def test_carries_the_heavy_recipe_from_the_newest_snapshot_through_its_base_receipt(self):
        record = self.carry()
        self.assertEqual(record['snapshot'], 'testing-f45-20261113.1')
        item = record['packages']['firefox']
        self.assertEqual(item['receipt_snapshot'], 'testing-f45-20261112.4')
        self.assertEqual(item['recipe_inputs'], fedoralib.recipe_inputs(self.root, 'firefox', 45))
        self.assertEqual(sorted(f['filename'] for f in item['files']), sorted(BINARIES))
        for name, data in BINARIES.items():
            self.assertEqual((self.output / name).read_bytes(), data)
        manifest = json.loads((self.output / 'manifest.json').read_text())
        self.assertEqual(manifest['signing_key'], 'F' * 40)
        self.assertEqual(sorted(r['filename'] for r in manifest['packages']), sorted(BINARIES))
        self.assertEqual(json.loads((self.output / 'carried.json').read_text()), record)
        # Only the heavy package's binaries are fetched, never the rest of the snapshot.
        self.assertNotIn(('testing-f45-20261113.1', 'mutter-50.1-1.fc45.aurora1.aarch64.rpm'), self.downloads)

    def test_a_snapshot_older_than_the_recipe_fails(self):
        (self.root / 'packages/firefox/f45/distgit.json').write_text('{"commit": "2"}\n')
        with self.assertRaises(module.StaleSnapshot) as error:
            self.carry()
        self.assertIn('older recipe', str(error.exception))
        self.assertIn('f45/distgit.json', str(error.exception))
        self.assertFalse((self.output / 'carried.json').exists())

    def test_a_patch_added_without_a_release_bump_is_stale(self):
        (self.root / 'packages/firefox/new.patch').write_text('fix\n')
        with self.assertRaises(module.StaleSnapshot):
            self.carry()

    def test_nothing_is_carried_when_the_run_built_the_heavy_recipe(self):
        self.built('firefox')
        self.assertIsNone(self.carry())
        self.assertFalse(self.output.exists())
        self.assertEqual(self.downloads, [])

    def test_a_snapshot_missing_the_receipt_rpms_fails(self):
        self.snapshot('testing-f45-20261113.2', base='testing-f45-20261113.1', receipts=[],
                      files={'firefox-159.0-1.fc45.aarch64.rpm': RPM})
        with self.assertRaises(module.StaleSnapshot) as error:
            self.carry()
        self.assertIn('does not carry', str(error.exception))

    def test_bytes_differing_from_the_manifest_fail(self):
        self.assets['testing-f45-20261113.1']['firefox-160.0-1.fc45.aurora2.aarch64.rpm'] = b'tampered\n'
        with self.assertRaises(module.StaleSnapshot):
            self.carry()

    def test_no_receipt_in_the_snapshot_chain_fails(self):
        self.releases = [r for r in self.releases if r['tag_name'] != 'testing-f45-20261112.4']
        with self.assertRaises(module.StaleSnapshot) as error:
            self.carry()
        self.assertIn('no Fedora 45 build receipt', str(error.exception))

    def test_fedora_44_snapshots_and_drafts_are_ignored(self):
        self.releases.append({'id': 99, 'tag_name': 'testing-20261114.1', 'draft': False,
                              'created_at': '2026-11-30T00:00:00Z', 'assets': []})
        self.releases.append({'id': 100, 'tag_name': 'testing-f45-20261114.1', 'draft': True,
                              'created_at': '2026-11-30T00:00:00Z', 'assets': []})
        self.assertEqual(self.carry()['snapshot'], 'testing-f45-20261113.1')

    def test_no_snapshot_fails(self):
        self.releases = []
        with self.assertRaises(module.StaleSnapshot):
            self.carry()


if __name__ == '__main__':
    unittest.main()
