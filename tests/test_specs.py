from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
class SpecTests(unittest.TestCase):
    def test_declared_local_sources_and_patches_are_present(self):
        for spec in (ROOT / 'packages').glob('*/*.spec'):
            with self.subTest(spec=spec.name):
                for kind, value in re.findall(r'^(Source\d*|Patch\d*):\s+(\S+)', spec.read_text(), re.M):
                    if '%{' not in value and not value.startswith('http'):
                        self.assertTrue((spec.parent / value).is_file(), value)
    def test_noarch_recipes_do_not_claim_machine_specific_binaries(self):
        for name in ['aurora-audio', 'alsa-ucm-conf-aurora', 'aurora-release', 'aurora-logos']:
            text = (ROOT / 'packages' / name / (name + '.spec')).read_text()
            self.assertIn('BuildArch: noarch', text)
if __name__ == '__main__': unittest.main()
