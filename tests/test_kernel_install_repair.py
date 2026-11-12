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

    def run_repair(self, installed=True, args=(), locked=0, returncode=0, **env):
        """Run the repair; `locked` queries fail on the rpm lock before one succeeds."""
        rows = '\n'.join(f'{tid} {krel}' for tid, krel in self.kernels)
        probes = self.root / 'probes'
        self.stub('rpm', f'''case "$*" in
*"--quiet rpm"*) echo x >> {probes}; [ "$(wc -l < {probes})" -gt {locked} ] || {{ echo "error: can't create transaction lock on /var/lib/rpm/.rpm.lock (Resource temporarily unavailable)" >&2; exit 1; }} ;;
*update-m1n1*) echo {OWN_TID} ;;
*kernel-aurora-core*) {'printf "%s\\n" "' + rows + '"' if installed else 'echo "package kernel-aurora-core is not installed"; exit 1'} ;;
esac
''')
        env = {**os.environ, 'PATH': f'{self.bin}:{os.environ["PATH"]}',
               'AURORA_BLS_ENTRIES': str(self.entries), 'AURORA_MODULES_DIR': str(self.modules),
               'AURORA_RPM_WAIT_STEP': '0', **env}
        done = subprocess.run(['sh', str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, returncode, done.stderr)
        self.probes = len(probes.read_text().splitlines()) if probes.exists() else 0
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

    def test_after_the_transaction_it_waits_for_the_rpm_lock(self):
        # Started by %posttrans through systemd: dnf still holds the lock.
        self.kernel('7.3.0-20.fc45.aurora.aarch64', entry=True)
        self.kernel('7.3.0-27.fc45.aurora.aarch64')
        modules = self.modules
        self.assertEqual(self.run_repair(args=['--after-transaction'], locked=3), [
            f'add 7.3.0-27.fc45.aurora.aarch64 {modules}/7.3.0-27.fc45.aurora.aarch64/vmlinuz',
        ])
        self.assertEqual(self.probes, 4)

    def test_a_lock_that_never_clears_fails_the_unit_and_repairs_nothing(self):
        self.kernel('7.3.0-20.fc45.aurora.aarch64', entry=True)
        self.kernel('7.3.0-27.fc45.aurora.aarch64')
        self.assertEqual(self.run_repair(args=['--after-transaction'], locked=10**6, returncode=1,
                                         AURORA_RPM_WAIT_SECONDS='2', AURORA_RPM_WAIT_STEP='1'), [])

    def test_run_in_the_transaction_it_does_not_wait(self):
        # Without systemd (an image build) %posttrans runs it directly, as before.
        self.kernel('7.3.0-20.fc45.aurora.aarch64', entry=True)
        self.kernel('7.3.0-27.fc45.aurora.aarch64')
        self.assertEqual(len(self.run_repair(locked=5)), 1)
        self.assertEqual(self.probes, 0)

    def test_a_failed_kernel_install_does_not_fail_the_transaction(self):
        self.stub('kernel-install', f'echo "$@" >> {self.log}\nexit 1\n')
        self.kernel('7.3.0-20.fc45.aurora.aarch64', entry=True)
        self.kernel('7.3.0-27.fc45.aurora.aarch64')
        self.assertEqual(len(self.run_repair()), 1)


if __name__ == '__main__':
    unittest.main()
