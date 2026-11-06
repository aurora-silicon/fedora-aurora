"""aurora-sep's upgrade scriptlets relabel the driver's state files without
touching them. The SELinux module and the authselect offer themselves are
tested with their sources in aurora-silicon/linux tools/aurora-sep/tests."""
import re
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / 'packages/aurora-sep'

# Every file the apple_sep driver keeps in /var/lib (drivers/soc/apple:
# catacomb.rs, keybag.rs, refkey.rs, store.rs, xart_guard.rs).
STATE = [
    'apple-sep-catacomb-master.bin', 'apple-sep-catacomb-owner.bin',
    'apple-sep-catacomb-user.bin', 'aurora-sep-keybag.bin',
    'aurora-sep-refkey.bin', 'aurora-sep-refkey-v2.bin',
    'aurora-sep-host-state.bin', 'aurora-sep-xart-owned.bin',
    'aurora-sep-xart-allow-once.bin', 'aurora-sep-xart-policy-previous.bin',
]


class SpecScriptletTests(unittest.TestCase):
    def setUp(self):
        self.spec = (PKG / 'aurora-sep.spec').read_text()

    def test_upgrade_labels_an_installed_loader(self):
        post = self.spec[self.spec.index('%posttrans selinux'):self.spec.index('%files')]
        self.assertIn('restorecon %{_libexecdir}/aurora-sep-load', post)

    def test_upgrade_relabels_exactly_the_state_files_without_touching_them(self):
        post = self.spec[self.spec.index('%posttrans selinux'):self.spec.index('%files')]
        self.assertEqual(sorted(re.findall(r'/var/lib/([\w.-]+\.bin)', post)), sorted(STATE))
        self.assertIn('restorecon -F "$f"', post)
        for verb in ('rm ', 'mv ', 'cp ', 'truncate', '>"$f"'):
            self.assertNotIn(verb, post)


if __name__ == '__main__':
    unittest.main()
