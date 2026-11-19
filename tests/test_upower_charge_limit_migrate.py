from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/upower-aurora'
SCRIPT = PACKAGE / 'upower-charge-limit-migrate'
LEGACY = 'etc/udev/macsmc-battery.conf'
STATUS = 'var/lib/upower/charging-threshold-status'
RULE = 'etc/udev/rules.d/61-upower-charge-limit.rules'


class MigrationTests(unittest.TestCase):
    """The one-time hand-over of a limit saved by the old macsmc-battery helper."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / 'root'
        (self.root / 'var/lib/upower').mkdir(parents=True)
        self.calls = Path(self.temporary.name) / 'udevadm.log'
        self.udevadm = Path(self.temporary.name) / 'udevadm'
        self.fake_udevadm(0)

    def tearDown(self):
        self.temporary.cleanup()

    def fake_udevadm(self, status):
        self.udevadm.write_text(f'#!/bin/sh\necho "$*" >> {self.calls}\nexit {status}\n')
        self.udevadm.chmod(0o755)

    def write(self, name, text, mtime=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def run_script(self):
        env = dict(os.environ, UPOWER_MIGRATE_ROOT=str(self.root), UPOWER_MIGRATE_UDEVADM=str(self.udevadm))
        result = subprocess.run(['sh', str(SCRIPT)], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stderr

    def udev_calls(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def assert_migrated(self):
        self.assertFalse((self.root / LEGACY).exists())

    def test_without_the_old_file_nothing_changes(self):
        self.assertEqual(self.run_script(), '')
        self.assertEqual(sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*')),
                         ['var', 'var/lib', 'var/lib/upower'])
        self.assertEqual(self.udev_calls(), [])

    def test_default_limit_turns_upower_on(self):
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=80\n')
        self.run_script()
        status = self.root / STATUS
        # upowerd compares the whole file with "1".
        self.assertEqual(status.read_bytes(), b'1')
        self.assertEqual(status.stat().st_mode & 0o777, 0o640)
        self.assertFalse((self.root / RULE).exists())
        self.assertEqual(self.udev_calls(), [])
        self.assert_migrated()

    def test_other_limit_is_kept_as_charge_limit(self):
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=75\n')
        self.run_script()
        self.assertEqual((self.root / STATUS).read_bytes(), b'1')
        rule = (self.root / RULE).read_text()
        self.assertIn('SUBSYSTEM=="power_supply", KERNEL=="macsmc-battery", ENV{CHARGE_LIMIT}="70,75"\n', rule)
        self.assertEqual((self.root / RULE).stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.udev_calls(), [
            'control --reload',
            'trigger --settle --action=change --subsystem-match=power_supply --sysname-match=macsmc-battery'])
        self.assert_migrated()

    def test_every_saved_limit_below_100(self):
        for limit in range(1, 100):
            with self.subTest(limit=limit):
                (self.root / STATUS).unlink(missing_ok=True)
                (self.root / RULE).unlink(missing_ok=True)
                self.write(LEGACY, f'CHARGE_CONTROL_END_THRESHOLD={limit}\n')
                self.run_script()
                self.assertEqual((self.root / STATUS).read_bytes(), b'1')
                if limit == 80:
                    self.assertFalse((self.root / RULE).exists())
                else:
                    self.assertIn(f'ENV{{CHARGE_LIMIT}}="{max(limit - 5, 0)},{limit}"', (self.root / RULE).read_text())
                self.assert_migrated()

    def test_no_limit_leaves_upower_as_it_is(self):
        for text in ('CHARGE_CONTROL_END_THRESHOLD=100\n', 'CHARGE_CONTROL_END_THRESHOLD=\n', '',
                     'CHARGE_CONTROL_END_THRESHOLD=0\n', 'CHARGE_CONTROL_END_THRESHOLD=101\n',
                     'CHARGE_CONTROL_END_THRESHOLD=080\n', 'CHARGE_CONTROL_END_THRESHOLD=-5\n',
                     'CHARGE_CONTROL_END_THRESHOLD= 80\n', 'CHARGE_CONTROL_END_THRESHOLD=80 \n',
                     'CHARGE_CONTROL_END_THRESHOLD=8O\n', 'OTHER=80\n'):
            with self.subTest(text=text):
                self.write(LEGACY, text)
                self.run_script()
                self.assertFalse((self.root / STATUS).exists())
                self.assertFalse((self.root / RULE).exists())
                self.assert_migrated()

    def test_last_saved_value_wins(self):
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=100\nCHARGE_CONTROL_END_THRESHOLD=80\n')
        self.run_script()
        self.assertEqual((self.root / STATUS).read_bytes(), b'1')

    def test_upower_switched_off_after_the_last_save_stays_off(self):
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=80\n', mtime=1_700_000_000)
        self.write(STATUS, '0', mtime=1_700_000_100)
        self.run_script()
        self.assertEqual((self.root / STATUS).read_bytes(), b'0')
        self.assert_migrated()

    def test_upower_switched_off_before_the_last_save_is_turned_on(self):
        self.write(STATUS, '0', mtime=1_700_000_000)
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=80\n', mtime=1_700_000_100)
        self.run_script()
        self.assertEqual((self.root / STATUS).read_bytes(), b'1')
        self.assert_migrated()

    def test_upower_already_on_is_not_rewritten(self):
        status = self.write(STATUS, '1')
        before = status.stat()
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=80\n')
        self.run_script()
        after = status.stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        self.assert_migrated()

    def test_missing_state_directory_is_created(self):
        shutil.rmtree(self.root / 'var')
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=80\n')
        self.run_script()
        self.assertEqual((self.root / STATUS).read_bytes(), b'1')

    def test_second_run_changes_nothing(self):
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=90\n')
        self.run_script()
        files = {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns)
                 for p in self.root.rglob('*') if p.is_file()}
        calls = self.udev_calls()
        self.assertEqual(self.run_script(), '')
        self.assertEqual(files, {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns)
                                 for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(self.udev_calls(), calls)

    def test_interrupted_run_finishes_on_the_next(self):
        # The old file is removed last: a run cut short after the state was
        # written repeats without a second write or a udev reload.
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=90\n')
        self.run_script()
        files = {p: p.stat().st_mtime_ns for p in self.root.rglob('*') if p.is_file()}
        calls = self.udev_calls()
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=90\n')
        self.run_script()
        self.assertEqual(files, {p: p.stat().st_mtime_ns for p in self.root.rglob('*')
                                 if p.is_file() and p.relative_to(self.root).as_posix() != LEGACY})
        self.assertEqual(self.udev_calls(), calls)
        self.assert_migrated()

    def test_old_restore_rule_still_installed_blocks_the_migration(self):
        for directory in ('usr/lib/udev/rules.d', 'etc/udev/rules.d', 'run/udev/rules.d'):
            with self.subTest(directory=directory):
                rule = self.write(f'{directory}/93-macsmc-battery-charge-control.rules', '# old\n')
                self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=80\n')
                self.assertIn('still installed', self.run_script())
                self.assertTrue((self.root / LEGACY).exists())
                self.assertFalse((self.root / STATUS).exists())
                rule.unlink()

    def test_udev_failure_keeps_the_migration(self):
        self.fake_udevadm(1)
        self.write(LEGACY, 'CHARGE_CONTROL_END_THRESHOLD=90\n')
        self.assertIn('applies from the next boot', self.run_script())
        self.assertIn('"85,90"', (self.root / RULE).read_text())
        self.assert_migrated()

    def test_unit_runs_before_upower_only_while_the_old_file_exists(self):
        unit = (PACKAGE / 'upower-charge-limit-migrate.service').read_text()
        self.assertIn('ConditionPathExists=/etc/udev/macsmc-battery.conf\n', unit)
        self.assertIn('Before=upower.service\n', unit)
        self.assertIn('Type=oneshot\n', unit)
        self.assertIn('ExecStart=/usr/libexec/aurora/upower-charge-limit-migrate\n', unit)

    @unittest.skipUnless(shutil.which('shellcheck'), 'shellcheck is not installed')
    def test_script_passes_shellcheck(self):
        subprocess.run(['shellcheck', '-s', 'sh', str(SCRIPT)], check=True)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.spec = (PACKAGE / 'upower-aurora.spec').read_text()

    def test_upower_replaces_asahi_battery(self):
        # asahi-battery is a subpackage of Fedora's asahi-scripts, versioned by date.
        self.assertRegex(self.spec, r'(?m)^Obsoletes: asahi-battery < 20270101$')
        self.assertRegex(self.spec, r'(?m)^Conflicts: asahi-battery$')

    def test_the_migration_runs_before_upowerd(self):
        self.assertRegex(self.spec, r'(?m)^Source1: upower-charge-limit-migrate$')
        self.assertRegex(self.spec, r'(?m)^Source2: upower-charge-limit-migrate.service$')
        install = self.spec.split('%install', 1)[1].split('%post', 1)[0]
        self.assertIn('install -Dpm0755 %{SOURCE1} %{buildroot}%{_libexecdir}/aurora/upower-charge-limit-migrate\n', install)
        self.assertIn('install -Dpm0644 %{SOURCE2} %{buildroot}%{_unitdir}/upower-charge-limit-migrate.service\n', install)
        # A static wants link: the unit runs whenever upower.service starts, also on D-Bus activation.
        self.assertIn('ln -s ../upower-charge-limit-migrate.service %{buildroot}%{_unitdir}/upower.service.wants/\n',
                      install)
        files = self.spec.split('%files -f upower.lang', 1)[1].split('%files libs', 1)[0]
        for line in ('%{_unitdir}/upower-charge-limit-migrate.service',
                     '%{_unitdir}/upower.service.wants/upower-charge-limit-migrate.service',
                     '%{_libexecdir}/aurora/upower-charge-limit-migrate'):
            self.assertRegex(files, rf'(?m)^{re.escape(line)}$')

    def test_the_upgrade_test_replaces_asahi_battery(self):
        test = (ROOT / 'scripts/test-upower-upgrade').read_text()
        self.assertIn('dnf install -y python3-rpm asahi-battery "${packages[@]}"', test)
        self.assertIn('rpm -q asahi-battery', test)
        self.assertIn('/usr/lib/systemd/system/upower.service.wants/upower-charge-limit-migrate.service', test)
