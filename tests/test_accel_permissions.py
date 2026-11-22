"""The Neural Engine node's permissions on every install, not only with the ANE tools."""
import fnmatch
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / 'packages' / 'aurora-platform'
TOOLS = ROOT / 'packages' / 'omarchy-ane-tools'

# systemd's own rule for the subsystem (50-udev-default.rules), and the file
# that runs the uaccess builtin for nodes tagged uaccess.
SYSTEMD_RULES = {
    '50-udev-default.rules': 'SUBSYSTEM=="accel", GROUP="render", MODE="0666"\n',
}
SEAT_LATE = '73-seat-late.rules'
TOKEN = re.compile(r'([A-Z_]+(?:\{[^}]*\})?)\s*(==|!=|\+=|-=|:=|=)\s*"([^"]*)"')


def rules(text):
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            yield TOKEN.findall(line)


def matches(pattern, value):
    return any(fnmatch.fnmatchcase(value, alt) for alt in pattern.split('|'))


def apply(files, device):
    """Group, mode and tags that udev leaves on device after the files, in name order."""
    state = {'GROUP': 'root', 'MODE': '0600', 'TAG': set()}
    for name in sorted(files):
        for tokens in rules(files[name]):
            ok = True
            for key, op, value in tokens:
                if op == '==':
                    ok = ok and matches(value, device.get(key, ''))
                elif op == '!=':
                    ok = ok and not matches(value, device.get(key, ''))
            if not ok:
                continue
            for key, op, value in tokens:
                if key == 'TAG' and op == '+=':
                    state['TAG'].add(value)
                elif key in ('GROUP', 'MODE') and op in ('=', ':='):
                    state[key] = value
    return state


def rule_files(directory):
    return {p.name: p.read_text() for p in directory.iterdir() if p.name.endswith('.rules')}


def section(spec, start, end):
    return spec.split(start, 1)[1].split(end, 1)[0]


class AccelPermissionTests(unittest.TestCase):
    NODE = {'SUBSYSTEM': 'accel', 'KERNEL': 'accel0'}

    def test_platform_core_restricts_the_node_to_accel_and_the_session_user(self):
        files = dict(SYSTEMD_RULES)
        files.update(rule_files(PLATFORM))
        state = apply(files, self.NODE)
        self.assertEqual((state['GROUP'], state['MODE']), ('accel', '0660'))
        self.assertIn('uaccess', state['TAG'])
        # The tag must be set before the seat rules act on it.
        accel = [n for n, t in files.items() if 'SUBSYSTEM=="accel"' in t and n not in SYSTEMD_RULES]
        self.assertEqual(accel, ['70-aurora-accel.rules'])
        self.assertLess(accel[0], '71-seat.rules')
        self.assertLess(accel[0], SEAT_LATE)
        # Other accel nodes get the same policy; nothing else does.
        self.assertEqual(apply(files, {'SUBSYSTEM': 'accel', 'KERNEL': 'accel3'})['MODE'], '0660')
        self.assertEqual(apply(files, {'SUBSYSTEM': 'drm', 'KERNEL': 'renderD128'})['GROUP'], 'root')

    def test_platform_core_installs_the_rule_and_the_group(self):
        spec = (PLATFORM / 'aurora-platform.spec').read_text()
        self.assertRegex(spec, r'(?m)^Source\d+: 70-aurora-accel\.rules$')
        self.assertRegex(spec, r'(?m)^Source\d+: aurora-accel\.sysusers$')
        install = section(spec, '%install', '%posttrans core')
        self.assertIn('%{buildroot}%{_udevrulesdir}/70-aurora-accel.rules', install)
        self.assertIn('%{buildroot}%{_sysusersdir}/aurora-accel.conf', install)
        core_files = section(spec, '%files core', '%files kdump')
        self.assertIn('%{_udevrulesdir}/70-aurora-accel.rules\n', core_files)
        self.assertIn('%{_sysusersdir}/aurora-accel.conf\n', core_files)
        sysusers = [l.split() for l in (PLATFORM / 'aurora-accel.sysusers').read_text().splitlines()
                    if l and not l.startswith('#')]
        self.assertEqual(sysusers, [['g', 'accel', '-']])
        # An existing node is fixed on upgrade, not only after a reboot.
        post = section(spec, '%post core\n', '\n%')
        self.assertIn('udevadm trigger --action=change --subsystem-match=accel', post)

    def test_images_install_platform_core(self):
        spec = (PLATFORM / 'aurora-platform.spec').read_text()
        self.assertIn('Requires: aurora-platform-core = %{version}-%{release}', spec)
        self.assertIn('"aurora-platform"', (ROOT / 'images' / 'configure.py').read_text())

    def test_the_ane_tools_carry_no_device_policy(self):
        spec = (TOOLS / 'omarchy-ane-tools.spec').read_text()
        self.assertEqual(rule_files(TOOLS), {})
        self.assertNotIn('_udevrulesdir', spec)
        self.assertNotIn('_sysusersdir', spec)
        self.assertRegex(spec, r'(?m)^Requires: aurora-platform-core >= 44-49$')

    def test_no_other_package_sets_accel_permissions(self):
        owners = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'packages').rglob('*.rules')
                        if 'SUBSYSTEM=="accel"' in p.read_text())
        self.assertEqual(owners, ['packages/aurora-platform/70-aurora-accel.rules'])


if __name__ == '__main__':
    unittest.main()
