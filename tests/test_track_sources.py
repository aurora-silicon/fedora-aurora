import datetime
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('track_sources', ROOT / 'scripts/track-sources.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NEW = 'c' * 40
TODAY = datetime.date(2026, 10, 23)


class FedoraSpecTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in module.RECIPES.values():
            shutil.copytree(ROOT / 'packages' / name, self.root / 'packages' / name)
        self.pins = json.loads((ROOT / 'sources.json').read_text())

    def spec(self, name):
        return (self.root / 'packages' / name / f'{name}.spec').read_text()

    def item(self, key, **extra):
        root = self.pins[key]['archive_root'].replace(self.pins[key]['commit'], NEW)
        return {'key': key, 'old': self.pins[key]['commit'], 'new': NEW, 'repository': 'aurora-silicon/x',
                'branch': 'main', 'archive_root': root, 'new_subject': 'Merge pull request #1', **extra}

    def test_aura_bumps_release_and_records_a_changelog_entry(self):
        before = int(module.tl.spec_field(self.spec('aura'), 'Release').split('%')[0])
        notes = module.update_recipe(self.root, self.item('aura'), TODAY)
        text = self.spec('aura')
        self.assertIn(f'%global commit {NEW}\n', text)
        self.assertIn(f'%autosetup -n aura-{NEW}\n', text)
        self.assertEqual(int(module.tl.spec_field(text, 'Release').split('%')[0]), before + 1)
        self.assertIn(f'%changelog\n* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-{before + 1}\n'
                      f'- Track aurora-silicon/x main at {NEW[:7]}.\n', text)
        self.assertEqual(notes, [])

    def test_kernel_release_candidate_uses_an_rpm_safe_version_and_resets_release(self):
        item = self.item('kernel-aurora', version='7.9.0-rc1')
        notes = module.update_recipe(self.root, item, TODAY)
        text = self.spec('kernel-aurora')
        self.assertEqual(module.tl.spec_field(text, 'Version'), '7.9.0~rc1')
        self.assertTrue(module.tl.spec_field(text, 'Release').startswith('1%{?dist}'))
        self.assertTrue(any('Version' in note for note in notes))

    def test_mismatched_unpack_directory_needs_review(self):
        item = self.item('kernel-aurora', version=self.pins['kernel-aurora']['version'])
        item['archive_root'] = 'linux-' + NEW
        module.update_recipe(self.root, item, TODAY)
        self.assertTrue(item.get('needs_review'))

    def test_mesa_keeps_its_numeric_version(self):
        item = self.item('mesa-aurora', version='26.3.0', upstream_version='26.3.0-devel')
        module.update_recipe(self.root, item, TODAY)
        self.assertEqual(module.tl.spec_field(self.spec('mesa-aurora'), 'Version'), '26.3.0')

    def test_tracked_sources_have_specs(self):
        tracking = json.loads((ROOT / 'tracking.json').read_text())
        self.assertEqual(set(tracking['sources']), set(module.RECIPES))


if __name__ == '__main__':
    unittest.main()
