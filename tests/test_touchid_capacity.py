# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise ENOSPC through the patched driver and fprintd using fake storage."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FPRINTD = ROOT / 'packages/fprintd'
LIBFPRINT = ROOT / 'packages/libfprint'


class TouchIdCapacityTests(unittest.TestCase):
    def test_enospc_reports_full_without_collecting_any_sep_print(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            # Only these unchanged upstream functions are needed. Apply the
            # production patch, not a reimplementation of the fixed callback.
            shutil.copytree(ROOT / 'tests/fixtures/fprintd-1.94.5', source, dirs_exist_ok=True)
            subprocess.run(['git', 'apply', str(FPRINTD / '0004-aurora-report-data-full-without-garbage-collection.patch')],
                           cwd=source, check=True)
            # Patch1000 creates the whole driver. The include filter avoids
            # needing unrelated libfprint files while applying the entire
            # driver's production patch stack in the RPM's order.
            spec = (LIBFPRINT / 'libfprint.spec').read_text()
            patches = re.findall(r'^Patch\d+:\s+(\S+)', spec, re.M)
            for patch in patches:
                subprocess.run(['git', 'apply', '--include=libfprint/drivers/aurora/aurora.c',
                                str(LIBFPRINT / patch)], cwd=source, check=True)
            self.assertRegex((source / 'libfprint/drivers/aurora/aurora.c').read_text(),
                             r'(?m)^#define FP_COMPONENT "apple-sep"$')
            subprocess.run(['python3', str(FPRINTD / 'test_enroll_capacity.py'),
                            str(source / 'src/device.c'), '--aurora',
                            str(source / 'libfprint/drivers/aurora/aurora.c'),
                            '--enroll-utils', str(source / 'utils/enroll.c')], check=True)

    def test_data_full_driver_requires_the_guarded_daemon(self):
        lib = (LIBFPRINT / 'libfprint.spec').read_text()
        daemon = (FPRINTD / 'fprintd.spec').read_text()
        self.assertRegex(lib, r'(?m)^Requires:\s+fprintd\(aurora-no-enroll-gc\) >= 1$')
        self.assertRegex(daemon, r'(?m)^Provides:\s+fprintd\(aurora-no-enroll-gc\) = 1$')
        self.assertIn('python3 %{SOURCE2} src/device.c --enroll-utils utils/enroll.c', daemon)


if __name__ == '__main__':
    unittest.main()
