"""kernel-install-repair finishes the kernels an older updater left without a
boot entry, newest last, and leaves everything else alone."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'packages/update-m1n1/kernel-install-repair'
OWN_TID = '200'


class KernelInstallRepairTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.entries = self.root / 'entries'
        self.modules = self.root / 'modules'
        self.bin = self.root / 'bin'
        for path in (self.entries, self.modules, self.bin):
            path.mkdir()
        self.log = self.root / 'kernel-install.log'
        self.kernels = []
        self.stub('kernel-install', f'echo "$@" >> {self.log}\n')

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/sh\n' + body)
        path.chmod(0o755)

    def kernel(self, krel, tid='100', entry=False, image=True):
        self.kernels.append((tid, krel))
        if image:
            (self.modules / krel).mkdir()
            (self.modules / krel / 'vmlinuz').write_bytes(b'image')
        if entry:
            (self.entries / f'abc-{krel}.conf').write_text(f'title Aurora\nversion {krel}\n')

    def run_repair(self, installed=True):
        rows = '\n'.join(f'{tid} {krel}' for tid, krel in self.kernels)
        self.stub('rpm', f'''case "$*" in
*update-m1n1*) echo {OWN_TID} ;;
*kernel-aurora-core*) {'printf "%s\\n" "' + rows + '"' if installed else 'echo "package kernel-aurora-core is not installed"; exit 1'} ;;
esac
''')
        env = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}',
                   AURORA_BLS_ENTRIES=str(self.entries), AURORA_MODULES_DIR=str(self.modules))
        done = subprocess.run(['sh', str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_kernels_newer_than_the_booted_one_are_finished_newest_last(self):
        # A J493: 7.3.0-20 boots, -26 and -27 were refused, -18 is older.
        self.kernel('7.3.0-27.fc45.aurora.aarch64')
        self.kernel('7.3.0-18.fc45.aurora.aarch64')
        self.kernel('7.3.0-20.fc45.aurora.aarch64', entry=True)
        self.kernel('7.3.0-26.fc45.aurora.aarch64')
        modules = self.modules
        self.assertEqual(self.run_repair(), [
            f'add 7.3.0-26.fc45.aurora.aarch64 {modules}/7.3.0-26.fc45.aurora.aarch64/vmlinuz',
            f'add 7.3.0-27.fc45.aurora.aarch64 {modules}/7.3.0-27.fc45.aurora.aarch64/vmlinuz',
        ])

    def test_an_older_kernel_without_an_entry_does_not_take_the_default(self):
        self.kernel('7.3.0-26.fc45.aurora.aarch64')
        self.kernel('7.3.0-28.fc45.aurora.aarch64', entry=True)
        self.assertEqual(self.run_repair(), [])

    def test_a_kernel_from_this_transaction_is_left_to_its_own_posttrans(self):
        self.kernel('7.3.0-20.fc45.aurora.aarch64', entry=True)
        self.kernel('7.3.0-28.fc45.aurora.aarch64', tid=OWN_TID)
        self.assertEqual(self.run_repair(), [])

    def test_a_kernel_without_its_image_is_skipped(self):
        self.kernel('7.3.0-20.fc45.aurora.aarch64', entry=True)
        self.kernel('7.3.0-27.fc45.aurora.aarch64', image=False)
        self.assertEqual(self.run_repair(), [])

    def test_without_aurora_kernels_nothing_runs(self):
        self.assertEqual(self.run_repair(installed=False), [])

    def test_a_failed_kernel_install_does_not_fail_the_transaction(self):
        self.stub('kernel-install', f'echo "$@" >> {self.log}\nexit 1\n')
        self.kernel('7.3.0-20.fc45.aurora.aarch64', entry=True)
        self.kernel('7.3.0-27.fc45.aurora.aarch64')
        self.assertEqual(len(self.run_repair()), 1)


if __name__ == '__main__':
    unittest.main()
