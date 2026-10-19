"""An upgrade must select SELinux support from the target, not running kernel."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'packages/aurora-firstboot/90-aurora-selinux.conf'


class SELinuxDracutTests(unittest.TestCase):
    def test_target_with_selinux_adds_standard_hook_and_preserves_other_modules(self):
        self.assertEqual(self.resolve('CONFIG_SECURITY_SELINUX=y\n'), 'aurora-root selinux ')

    def test_old_rollback_kernel_does_not_gain_an_incompatible_hook(self):
        self.assertEqual(self.resolve('# CONFIG_SECURITY_SELINUX is not set\n'), 'aurora-root')

    def test_missing_target_configuration_does_not_assume_running_capabilities(self):
        self.assertEqual(self.resolve(None), 'aurora-root')

    def resolve(self, content):
        with tempfile.TemporaryDirectory() as directory:
            if content is not None:
                path = Path(directory) / 'usr/lib/modules/fixture-target/config'
                path.parent.mkdir(parents=True)
                path.write_text(content)
            return subprocess.check_output(['bash', '-eu', '-c',
                'dracutsysrootdir=$1; kernel=fixture-target; add_dracutmodules=aurora-root; source "$2"; printf %s "$add_dracutmodules"',
                'fixture', directory, str(CONFIG)], text=True)
