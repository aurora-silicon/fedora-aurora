"""Keep the pinned hardware fragment in both configuration and validation."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

KERNEL = Path(__file__).resolve().parents[1] / 'packages/kernel-aurora'


class UniversalKernelConfig(unittest.TestCase):
    def test_single_hardware_fragment_is_merged_and_validated(self):
        recipe = (KERNEL / 'kernel-aurora.spec').read_text()
        merge = next(line for line in recipe.splitlines() if line.startswith('scripts/kconfig/merge_config.sh'))
        validation = next(line for line in recipe.splitlines() if line.startswith('python3 %{SOURCE5}'))
        for line in (merge, validation):
            self.assertIn('arch/arm64/configs/asahi.config', line)
            self.assertIn('%{SOURCE4}', line)
        for name in ('neo.config', 'common.config'):
            self.assertNotIn(name, recipe)
            self.assertFalse((KERNEL / name).exists())

    def test_shared_radio_driver_cannot_be_silently_dropped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'shared').write_text('CONFIG_MT7932_FULLMAC=m\n')
            (root / 'policy').write_text('CONFIG_SECURITY_SELINUX=y\n')
            (root / 'resolved').write_text('CONFIG_SECURITY_SELINUX=y\n')
            result = subprocess.run([sys.executable, str(KERNEL / 'validate-config.py'),
                                     str(root / 'shared'), str(root / 'policy'), str(root / 'resolved')],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('CONFIG_MT7932_FULLMAC', result.stderr)


if __name__ == '__main__':
    unittest.main()
