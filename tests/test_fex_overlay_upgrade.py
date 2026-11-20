"""Run package lifecycle scriptlets against a stateful systemctl double."""
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class FexOverlayTests(unittest.TestCase):
    def run_lifecycle(self, active=True, stop_fails=False, start_fails=False, stale_mount=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'system').mkdir()
            if active:
                (root / 'active').touch()
                (root / 'mounted').touch()
            if stale_mount:
                (root / 'mounted').touch()
            ctl = root / 'systemctl'
            ctl.write_text("""#!/bin/bash
printf '%s\\n' "$*" >> "$TEST_ROOT/log"
case "$*" in
  *is-active*) test -e "$TEST_ROOT/active" ;;
  stop*) test "$STOP_FAILS" = no || exit 1; rm -f "$TEST_ROOT/active" "$TEST_ROOT/mounted" ;;
  start*) test "$START_FAILS" = no || exit 1; touch "$TEST_ROOT/active" ;;
  *) exit 0 ;;
esac
""")
            ctl.chmod(0o755)
            mountpoint = root / 'mountpoint'
            mountpoint.write_text('#!/bin/bash\ntest -e "$TEST_ROOT/mounted"\n')
            mountpoint.chmod(0o755)
            script = self.script().replace('/run/systemd/system', str(root / 'system')).replace('/run/aurora-fex-mesa.upgrade', str(root / 'marker'))
            env = dict(os.environ, PATH=tmp + ':' + os.environ['PATH'], TEST_ROOT=tmp,
                       STOP_FAILS='yes' if stop_fails else 'no', START_FAILS='yes' if start_fails else 'no')
            pre = subprocess.run(['bash', '-c', script + '\n' + self.pre()], env=env)
            if (stop_fails and active) or stale_mount:
                self.assertNotEqual(pre.returncode, 0)
                self.assertEqual((root / 'active').exists(), active)
                self.assertFalse((root / 'marker').exists())
                return
            self.assertEqual(pre.returncode, 0)
            self.assertFalse((root / 'active').exists())
            self.assertEqual((root / 'marker').exists(), active)
            post = subprocess.run(['bash', '-c', script + '\n' + self.post()], env=env)
            self.assertEqual((root / 'active').exists(), active and not start_fails)
            self.assertEqual((root / 'marker').exists(), active and start_fails)
            self.assertEqual(post.returncode == 0, not (active and start_fails))

    def test_running_service_is_stopped_and_restored(self):
        self.run_lifecycle()

    def test_inactive_service_stays_inactive(self):
        self.run_lifecycle(active=False)

    def test_failed_stop_is_reported_before_unpack(self):
        self.run_lifecycle(stop_fails=True)

    def test_stale_mount_is_reported_before_unpack(self):
        self.run_lifecycle(active=False, stale_mount=True)

    def test_failed_remount_retains_recovery_marker(self):
        self.run_lifecycle(start_fails=True)

    def script(self):
        text = (ROOT / 'packages/mesa-aurora-fex-guest/mesa-aurora-fex-guest.spec').read_text()
        pre = text.split('\n%pre\n', 1)[1].split('\n%post\n', 1)[0]
        post = text.split('\n%posttrans\n', 1)[1].split('\n%files', 1)[0]
        return 'pre() {\n' + pre + '\n}\npost() {\n' + post + '\n}'

    def pre(self):
        return 'pre 2'

    def post(self):
        return 'post'


FEX = ROOT / 'packages/fex-emu'
PROVIDER = '/usr/share/guestos/aurora-fex-mesa'

# Mount doubles over a stack of "path device busy" lines, newest last: enough
# to model the provider's overlay and its binds without mounting anything.
MOUNT_DOUBLES = {
    'mountpoint': '''#!/bin/bash
[[ $1 == -q ]] && shift
grep -q "^$1 " "$TEST_ROOT/mounts"
''',
    'umount': '''#!/bin/bash
printf 'umount %s\\n' "$*" >> "$TEST_ROOT/log"
line=$(grep -n "^$1 " "$TEST_ROOT/mounts" | tail -n1) || exit 32
[[ ${line##* } == 0 ]] || exit 32
sed -i "${line%%:*}d" "$TEST_ROOT/mounts"
''',
    'mount': '''#!/bin/bash
printf 'mount %s\\n' "$*" >> "$TEST_ROOT/log"
[[ ${MOUNT_FAILS:-no} == no ]] || exit 1
[[ $1 == --bind && $2 == -o && $3 == ro ]] || exit 2
dev=$(grep "^$4 " "$TEST_ROOT/mounts" | tail -n1 | cut -d' ' -f2)
echo "$5 ${dev:?} 0" >> "$TEST_ROOT/mounts"
''',
    'stat': '''#!/bin/bash
[[ $1 == -c && $2 == %d ]] || exit 2
dev=$(grep "^$3 " "$TEST_ROOT/mounts" | tail -n1 | cut -d' ' -f2)
echo "${dev:-root}"
''',
}


def write_doubles(directory, doubles):
    for name, text in doubles.items():
        path = Path(directory) / name
        path.write_text(text)
        path.chmod(0o755)


ELF64 = b'\x7fELF\x02\x01\x01\x00'
ELF32 = b'\x7fELF\x01\x01\x01\x00'
FEDORA_TREE = {'.aurora-mesa-commit': b'', 'usr/lib64/ld-linux-x86-64.so.2': ELF64,
               'usr/lib64/libvulkan_asahi.so': ELF64, 'usr/lib/libvulkan_asahi.so': ELF32}


class FexRootfsTests(unittest.TestCase):
    """aurora-fex-rootfs points FEX's global RootFS at the provider only while
    it is a usable tree, through a bind that FEX's programs can keep busy."""

    def run_select(self, mounts=(), files=FEDORA_TREE, config=False, mount_fails=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        provider, run = root / 'provider', root / 'run/fex-emu'
        for name, data in (files if isinstance(files, dict) else dict.fromkeys(files, b'')).items():
            (provider / name).parent.mkdir(parents=True, exist_ok=True)
            (provider / name).write_bytes(data)
        provider.mkdir(exist_ok=True)
        if config:
            run.mkdir(parents=True)
            (run / 'Config.json').write_text('{"Config": {"RootFS": "stale"}}\n')
        names = {'provider': str(provider), 'rootfs': str(run / 'rootfs')}
        (root / 'mounts').write_text(''.join(f'{names[p]} {d} {b}\n' for p, d, b in mounts))
        (root / 'log').touch()
        bin_dir = root / 'bin'
        bin_dir.mkdir()
        write_doubles(bin_dir, MOUNT_DOUBLES)
        script = (FEX / 'aurora-fex-rootfs').read_text()
        self.assertIn(f'provider={PROVIDER}\n', script)
        self.assertIn('dir=/run/fex-emu\n', script)
        script = script.replace(f'provider={PROVIDER}\n', f'provider={provider}\n')
        script = script.replace('dir=/run/fex-emu\n', f'dir={run}\n')
        env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}', TEST_ROOT=str(root),
                   MOUNT_FAILS='yes' if mount_fails else 'no')
        result = subprocess.run(['sh', '-c', script], env=env)
        stack = [line.split() for line in (root / 'mounts').read_text().splitlines()]
        reverse = {v: k for k, v in names.items()}
        stack = [(reverse[p], d, b) for p, d, b in stack]
        cfg = run / 'Config.json'
        rootfs_config = json.loads(cfg.read_text()) if cfg.exists() else None
        return result.returncode, stack, rootfs_config, (root / 'log').read_text(), str(run / 'rootfs'), run

    def assert_selected(self, rootfs_config, rootfs):
        self.assertEqual(rootfs_config, {'Config': {'RootFS': rootfs}})

    def test_mounted_provider_becomes_the_rootfs_through_a_bind(self):
        status, stack, cfg, log, rootfs, run = self.run_select(mounts=[('provider', 'ovl1', 0)])
        self.assertEqual(status, 0)
        self.assert_selected(cfg, rootfs)
        self.assertEqual(stack, [('provider', 'ovl1', '0'), ('rootfs', 'ovl1', '0')])
        self.assertIn(f'mount --bind -o ro {run.parent.parent}/provider {rootfs}\n', log)
        self.assertEqual(oct((run / 'Config.json').stat().st_mode & 0o777), '0o644')
        self.assertEqual([p.name for p in run.iterdir() if p.name.startswith('.')], [])

    def test_arch_guest_layout_is_usable(self):
        _, _, cfg, _, rootfs, _ = self.run_select(mounts=[('provider', 'ovl1', 0)], files={
            '.aurora-mesa-commit': b'', 'usr/lib/ld-linux-x86-64.so.2': ELF64,
            'usr/lib/libvulkan_asahi.so': ELF64, 'usr/lib32/libvulkan_asahi.so': ELF32})
        self.assert_selected(cfg, rootfs)

    def test_fedora_layer_over_an_arch_guest_is_not_used(self):
        # i686 Mesa in Arch's x86-64 usr/lib; x86-64 Mesa in a usr/lib64 the
        # guest's loader never searches (alarm-aurora#335).
        _, _, cfg, _, _, _ = self.run_select(mounts=[('provider', 'ovl1', 0)], files={
            '.aurora-mesa-commit': b'', 'usr/lib/ld-linux-x86-64.so.2': ELF64,
            'usr/lib/libvulkan_asahi.so': ELF32, 'usr/lib64/libvulkan_asahi.so': ELF64}, config=True)
        self.assertIsNone(cfg)

    def test_layer_without_its_x86_64_driver_is_not_used(self):
        tree = {k: v for k, v in FEDORA_TREE.items() if k != 'usr/lib64/libvulkan_asahi.so'}
        _, _, cfg, _, _, _ = self.run_select(mounts=[('provider', 'ovl1', 0)], files=tree)
        self.assertIsNone(cfg)

    def test_without_the_provider_fex_keeps_the_stock_image(self):
        status, stack, cfg, log, _, _ = self.run_select(config=True)
        self.assertEqual(status, 0)
        self.assertIsNone(cfg)
        self.assertEqual(stack, [])
        self.assertNotIn('mount --bind', log)

    def test_provider_without_its_lower_layer_is_not_used(self):
        # The overlay mounted over an empty lower directory holds only Mesa.
        tree = {k: v for k, v in FEDORA_TREE.items() if 'ld-linux' not in k}
        _, stack, cfg, _, _, _ = self.run_select(mounts=[('provider', 'ovl1', 0)], files=tree, config=True)
        self.assertIsNone(cfg)
        self.assertEqual(stack, [('provider', 'ovl1', '0')])

    def test_tree_without_the_aurora_layer_is_not_used(self):
        tree = {k: v for k, v in FEDORA_TREE.items() if k != '.aurora-mesa-commit'}
        _, _, cfg, _, _, _ = self.run_select(mounts=[('provider', 'ovl1', 0)], files=tree)
        self.assertIsNone(cfg)

    def test_current_bind_is_kept(self):
        _, stack, cfg, log, rootfs, _ = self.run_select(mounts=[('provider', 'ovl1', 0), ('rootfs', 'ovl1', 1)])
        self.assert_selected(cfg, rootfs)
        self.assertEqual(stack, [('provider', 'ovl1', '0'), ('rootfs', 'ovl1', '1')])
        self.assertEqual(log, '')

    def test_unused_stale_bind_is_replaced(self):
        _, stack, cfg, _, rootfs, _ = self.run_select(mounts=[('provider', 'ovl2', 0), ('rootfs', 'ovl1', 0)])
        self.assert_selected(cfg, rootfs)
        self.assertEqual(stack, [('provider', 'ovl2', '0'), ('rootfs', 'ovl2', '0')])

    def test_stale_bind_in_use_stays_below_the_new_one(self):
        # An x86 program still runs from the previous provider (an upgrade).
        _, stack, cfg, _, rootfs, _ = self.run_select(mounts=[('provider', 'ovl2', 0), ('rootfs', 'ovl1', 1)])
        self.assert_selected(cfg, rootfs)
        self.assertEqual(stack, [('provider', 'ovl2', '0'), ('rootfs', 'ovl1', '1'), ('rootfs', 'ovl2', '0')])

    def test_bind_in_use_survives_the_provider(self):
        status, stack, cfg, _, _, _ = self.run_select(mounts=[('rootfs', 'ovl1', 1)], config=True)
        self.assertEqual(status, 0)
        self.assertIsNone(cfg)
        self.assertEqual(stack, [('rootfs', 'ovl1', '1')])

    def test_unused_binds_go_with_the_provider(self):
        _, stack, cfg, _, _, _ = self.run_select(mounts=[('rootfs', 'ovl1', 0), ('rootfs', 'ovl2', 0)])
        self.assertIsNone(cfg)
        self.assertEqual(stack, [])

    def test_failed_bind_leaves_the_stock_image(self):
        status, _, cfg, _, _, _ = self.run_select(mounts=[('provider', 'ovl1', 0)], config=True, mount_fails=True)
        self.assertNotEqual(status, 0)
        self.assertIsNone(cfg)


class FexProviderUpTests(unittest.TestCase):
    """aurora-fex-provider-up restarts an enabled provider and always lets the
    RootFS follow the provider's state."""

    def run_up(self, systemd=True, enabled=True, lower_active=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'log').touch()
            if systemd:
                (root / 'system').mkdir()
            for flag, name in ((enabled, 'enabled'), (lower_active, 'lower-active')):
                if flag:
                    (root / name).touch()
            write_doubles(root, {'systemctl': '''#!/bin/bash
printf 'systemctl %s\\n' "$*" >> "$TEST_ROOT/log"
case "$*" in
  *is-enabled*) test -e "$TEST_ROOT/enabled" ;;
  *is-active*) test -e "$TEST_ROOT/lower-active" ;;
  *) exit 0 ;;
esac
''', 'rootfs': '#!/bin/bash\necho rootfs >> "$TEST_ROOT/log"\n'})
            script = (FEX / 'aurora-fex-provider-up').read_text()
            script = script.replace('/run/systemd/system', str(root / 'system'))
            self.assertIn('/usr/libexec/fex-emu/aurora-fex-rootfs', script)
            script = script.replace('/usr/libexec/fex-emu/aurora-fex-rootfs', str(root / 'rootfs'))
            env = dict(os.environ, PATH=f'{tmp}:{os.environ["PATH"]}', TEST_ROOT=tmp)
            self.assertEqual(subprocess.run(['sh', '-c', script], env=env).returncode, 0)
            return (root / 'log').read_text().splitlines()

    def test_enabled_provider_is_restarted_then_selected(self):
        log = self.run_up(lower_active=True)
        stop = log.index('systemctl stop aurora-fex-mesa.service usr-share-guestos-fex\\x2dmesa.mount')
        self.assertLess(stop, log.index('systemctl start aurora-fex-mesa.service'))
        self.assertEqual(log[-1], 'rootfs')

    def test_first_start_selects_the_rootfs(self):
        log = self.run_up()
        self.assertNotIn('systemctl stop', ' '.join(log))
        self.assertEqual(log[-2:], ['systemctl start aurora-fex-mesa.service', 'rootfs'])

    def test_disabled_provider_is_left_alone_but_followed(self):
        log = self.run_up(enabled=False)
        self.assertFalse([line for line in log if 'start' in line or 'stop' in line])
        self.assertEqual(log[-1], 'rootfs')

    def test_nothing_runs_without_systemd(self):
        self.assertEqual(self.run_up(systemd=False), [])


class FexScriptletTests(unittest.TestCase):
    """fex-emu's own scriptlets around the guest package and its removal."""

    def scriptlet(self, header):
        spec = (FEX / 'fex-emu.spec').read_text()
        body = spec.split('\n' + header + '\n', 1)[1]
        return re.split(r'\n%(?:files|trigger\w*|post\w*|pre\w*)\b', body, maxsplit=1)[0]

    def run_scriptlet(self, header, *args):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'log').touch()
            run = root / 'run/fex-emu'
            run.mkdir(parents=True)
            (run / 'Config.json').write_text('{}')
            write_doubles(root, {name: f'#!/bin/bash\necho "{name} $*" >> "$TEST_ROOT/log"\n'
                                 for name in ('systemctl', 'umount', 'rootfs')})
            (root / 'bin').mkdir()
            (root / 'bin/systemctl').symlink_to(root / 'systemctl')
            body = self.scriptlet(header).replace('%{_libexecdir}/fex-emu/aurora-fex-rootfs', str(root / 'rootfs'))
            body = body.replace('/run/fex-emu', str(run)).replace('/bin/systemctl', str(root / 'bin/systemctl'))
            env = dict(os.environ, PATH=f'{tmp}:{os.environ["PATH"]}', TEST_ROOT=tmp)
            status = subprocess.run(['sh', '-c', body, 'scriptlet', *args], env=env).returncode
            return status, (root / 'log').read_text().splitlines(), (run / 'Config.json').exists(), run

    def test_guest_removal_rechecks_the_rootfs(self):
        status, log, _, _ = self.run_scriptlet('%triggerpostun -- mesa-aurora-fex-guest', '1', '0')
        self.assertEqual((status, log), (0, ['rootfs ']))

    def test_guest_upgrade_leaves_the_rootfs_to_its_service(self):
        status, log, _, _ = self.run_scriptlet('%triggerpostun -- mesa-aurora-fex-guest', '1', '1')
        self.assertEqual((status, log), (0, []))

    def test_erase_drops_the_runtime_config_and_an_unused_bind(self):
        status, log, config, run = self.run_scriptlet('%postun', '0')
        self.assertEqual(status, 0)
        self.assertFalse(config)
        self.assertIn(f'umount {run}/rootfs', log)

    def test_upgrade_keeps_the_runtime_config(self):
        status, log, config, _ = self.run_scriptlet('%postun', '1')
        self.assertEqual((status, log, config), (0, [], True))
