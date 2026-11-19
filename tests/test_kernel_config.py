"""Keep the pinned hardware fragment in both configuration and validation."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

KERNEL = Path(__file__).resolve().parents[1] / 'packages/kernel-aurora'


class UniversalKernelConfig(unittest.TestCase):
    def test_the_kernel_source_configuration_is_used_unchanged(self):
        recipe = (KERNEL / 'kernel-aurora.spec').read_text().split('%changelog', 1)[0]
        lines = recipe.splitlines()
        configure = [line for line in lines if 'aurora_defconfig' in line and line.startswith('make ')]
        self.assertEqual(len(configure), 1)
        validation = next(line for line in lines if line.startswith('python3 %{SOURCE5}'))
        self.assertIn('arch/arm64/configs/aurora-base.config', validation)
        self.assertIn('arch/arm64/configs/asahi.config', validation)
        # No packaged base or overlay: every distribution builds the same options.
        self.assertNotIn('merge_config.sh', recipe)
        self.assertNotIn('scripts/config', recipe)
        self.assertNotIn('olddefconfig', recipe)
        for name in ('config', 'fedora.config', 'neo.config', 'common.config'):
            self.assertFalse((KERNEL / name).exists(), name)

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
