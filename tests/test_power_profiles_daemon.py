import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PowerProfilesDaemonTest(unittest.TestCase):
    def test_f44_and_f45_specs_carry_platform_profile_class_patch(self):
        patch_name = '0001-platform-profile-use-the-class-interface-without-acpi.patch'
        patch = ROOT / 'packages/power-profiles-daemon' / patch_name
        self.assertTrue(patch.is_file())
        self.assertIn('/sys/class/platform-profile', patch.read_text())

        f44 = (ROOT / 'packages/power-profiles-daemon/power-profiles-daemon.spec').read_text()
        f45 = (ROOT / 'packages/power-profiles-daemon/f45/power-profiles-daemon.spec').read_text()

        self.assertIn('Release:        3%{?dist}.aurora1', f44)
        self.assertIn('Release:        4%{?dist}.aurora1', f45)
        for text in (f44, f45):
            self.assertIn('Version:        0.30', text)
            self.assertIn(f'Patch0:         {patch_name}', text)
            self.assertIn('%meson_test', text)
            self.assertIn('Provides:       ppd-service', text)
            self.assertIn('Conflicts:      ppd-service', text)

    def test_sources_and_vendor_policy_include_power_profiles_daemon(self):
        root_sources = json.loads((ROOT / 'sources.json').read_text())
        f45_sources = json.loads((ROOT / 'packages/power-profiles-daemon/f45/sources.json').read_text())
        self.assertIn('power-profiles-daemon', root_sources)
        self.assertEqual(root_sources['power-profiles-daemon'], f45_sources['power-profiles-daemon'])
        self.assertEqual(root_sources['power-profiles-daemon']['version'], '0.30')

        conf = (ROOT / 'packages/aurora-repos/aurora-vendors-unvendored.conf').read_text()
        self.assertIn("{ filter = 'source_name', value = 'power-profiles-daemon' }", conf)


if __name__ == '__main__':
    unittest.main()
