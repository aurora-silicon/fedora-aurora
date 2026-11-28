import configparser
import json
from pathlib import Path
import os
import re
import shlex
import shutil
import struct
import subprocess
import tempfile
import time
import unittest
ROOT = Path(__file__).resolve().parents[1]


def distgit_inputs(directory):
    """Files a dist-git import fetches at build time (scripts/fetch-fedora-lookaside.py)."""
    if not (directory / 'distgit.json').is_file():
        return set()
    names = set(json.loads((directory / 'distgit.json').read_text()).get('fetch', {}))
    return names | set(re.findall(r'^SHA512 \(([^)]+)\) = ', (directory / 'sources').read_text(), re.M))


# systemd-binfmt's configuration directories, the first winning a file name.
BINFMT_DIRS = ('/etc/binfmt.d', '/run/binfmt.d', '/usr/local/lib/binfmt.d', '/usr/lib/binfmt.d')


def binfmt_registrations(tree):
    """binfmt_misc's handlers, newest first, as systemd-binfmt leaves them.

    tree maps a directory to {file name: text}. systemd-binfmt flushes every
    handler, then reads the files in file-name order, each name from the
    first directory that has it, and registers each rule after removing a
    handler of the same name. The kernel puts a new handler first and runs
    the first that matches, so the last registered wins.
    """
    files = {}
    for directory in reversed(BINFMT_DIRS):
        files.update(tree.get(directory, {}))
    handlers = []
    for name in sorted(files):
        for line in files[name].splitlines():
            line = line.strip()
            if not line or line[0] in '#;':
                continue
            rule, kind, offset, magic, mask, interpreter, flags = line[1:].split(line[0])[:7]
            assert kind == 'M', line
            # binfmt_misc reads \xHH as that byte, any other character as itself.
            unescape = lambda s: re.sub(rb'\\x([0-9a-fA-F]{2})', lambda m: bytes([int(m[1], 16)]), s.encode())
            handlers = [h for h in handlers if h['name'] != rule]
            handlers.insert(0, {'name': rule, 'offset': int(offset or 0), 'magic': unescape(magic),
                                'mask': unescape(mask), 'interpreter': interpreter, 'flags': flags})
    return handlers


def binfmt_handler(handlers, header):
    """The handler binfmt_misc runs for a file that starts with header."""
    for h in handlers:
        data = header[h['offset']:h['offset'] + len(h['magic'])]
        if len(data) == len(h['magic']) and all((d ^ m) & k == 0 for d, m, k in zip(data, h['magic'], h['mask'])):
            return h
    return None


def x86_elf_header(bits, e_type=2):
    """The ELF header of an x86 (32) or x86-64 (64) executable, up to e_machine."""
    ident = b'\x7fELF' + bytes([1 if bits == 32 else 2, 1, 1]) + bytes(9)
    return ident + struct.pack('<HH', e_type, 3 if bits == 32 else 62)


def fex_guest_argv(args, fd, at_flags=0):
    """The arguments FEX gives the x86 program: FEX's own argv after argv[0].

    FEX loads the program from fd (binfmt_misc's AT_EXECFD, or FEX_EXECVEFD)
    when there is one, else from args[0]; the program's argv is args, without
    args[0] when it loaded from an fd or binfmt_misc preserved argv[0]
    (AT_FLAGS_PRESERVE_ARGV0), the layout binfmt_misc's P flag gives (FEX's
    ELFCodeLoader).
    """
    return args[1:] if fd or at_flags & 1 else args


class SpecTests(unittest.TestCase):
    def test_declared_local_sources_and_patches_are_present(self):
        pins = json.loads((ROOT / 'sources.json').read_text())
        for spec in (ROOT / 'packages').glob('*/*.spec'):
            extras = pins.get(spec.parent.name, {}).get('extra_sources', {})
            fetched = {record.get("archive_file", f"{name}-{record['commit']}.tar.gz") for name, record in extras.items()}
            fetched |= distgit_inputs(spec.parent)
            with self.subTest(spec=spec.name):
                for kind, value in re.findall(r'^(Source\d*|Patch\d*):\s+(\S+)', spec.read_text(), re.M):
                    if '%{' not in value and not value.startswith('http') and value not in fetched:
                        self.assertTrue((spec.parent / value).is_file(), value)
    def test_noarch_recipes_do_not_claim_machine_specific_binaries(self):
        for name in ['aurora-audio', 'alsa-ucm-conf-aurora', 'aurora-release', 'aurora-repos', 'aurora-logos']:
            text = (ROOT / 'packages' / name / (name + '.spec')).read_text()
            self.assertIn('BuildArch: noarch', text)
    def test_release_identity_is_named_aurora_fedora_remix(self):
        # The standard Fedora Remix naming; the Fedora-compatible IDs stay.
        d = ROOT / 'packages' / 'aurora-release'
        fields = dict(line.split('=', 1) for line in (d / 'os-release').read_text().splitlines() if '=' in line)
        self.assertEqual(fields['NAME'], '"Aurora Fedora Remix"')
        self.assertEqual(fields['PRETTY_NAME'], '"Aurora Fedora Remix 44"')
        self.assertEqual((fields['ID'], fields['VARIANT_ID'], fields['LOGO']), ('fedora', 'aurora', 'aurora-logo-icon'))
        self.assertEqual((d / 'system-release').read_text(), 'Aurora Fedora Remix release 44\n')
    def test_plasma_launcher_icon_is_kde_artwork_not_the_distribution_logo(self):
        # The launcher's start-here is KDE's artwork and never missing; the
        # Aurora logo stays the distribution logo.
        d = ROOT / 'packages' / 'aurora-logos'
        text = (d / 'aurora-logos.spec').read_text()
        files = text.split('%files', 1)[1].split('%changelog', 1)[0]
        self.assertIn('%{_datadir}/icons/hicolor/*/places/start-here.svg', files)
        self.assertNotIn('start-here.png', text)
        installed = re.findall(r'breeze-start-here-kde-\$size\.svg \\\n\s+(\S+)', text)
        self.assertEqual(installed, ['%{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/places/start-here.svg',
                                     '%{buildroot}%{_datadir}/icons/hicolor/${size}x${size}@2/places/start-here.svg'])
        for size in (16, 22, 24, 32, 64, 96):
            self.assertIn('class="ColorScheme-Text"', (d / f'breeze-start-here-kde-{size}.svg').read_text())
        self.assertRegex(text, r'(?m)^License: MIT AND LGPL-3\.0-or-later$')
        self.assertIn('%license breeze-COPYING-ICONS', files)
        self.assertIn('version 3 of the License, or (at your option) any later version', (d / 'breeze-COPYING-ICONS').read_text())
        self.assertIn('AuroraLogo-256.png %{buildroot}%{_datadir}/pixmaps/system-logo-white.png', text)
    def test_release_presets_sshd_off_ahead_of_fedora_default(self):
        # Fedora's 90-default.preset enables sshd.service; the desktop
        # identities that turned it off are replaced by aurora-release.
        d = ROOT / 'packages' / 'aurora-release'
        preset = d / '80-aurora-sshd.preset'
        rules = [line for line in preset.read_text().splitlines() if line.strip() and not line.startswith('#')]
        self.assertEqual(rules, ['disable sshd.service', 'disable sshd.socket'])
        self.assertLess(preset.name, '90-default.preset')
        text = (d / 'aurora-release.spec').read_text()
        self.assertRegex(text, r'(?m)^Source\d+: 80-aurora-sshd\.preset$')
        self.assertIn('%{buildroot}/usr/lib/systemd/system-preset/80-aurora-sshd.preset', text)
        self.assertIn('/usr/lib/systemd/system-preset/*.preset', text.split('%files', 1)[1])
    def test_release_presets_keep_what_the_image_enables(self):
        # systemd applies the presets on the first boot, before / is writable.
        d = ROOT / 'packages' / 'aurora-release'
        preset = d / '80-aurora-image.preset'
        rules = [line for line in preset.read_text().splitlines() if line.strip() and not line.startswith('#')]
        self.assertEqual(rules, ['enable graphical.target', 'enable multi-user.target',
                                 'enable systemd-resolved-monitor.socket', 'enable systemd-resolved-varlink.socket'])
        self.assertLess(preset.name, '99-default-disable.preset')
        text = (d / 'aurora-release.spec').read_text()
        self.assertRegex(text, r'(?m)^Source\d+: 80-aurora-image\.preset$')
        self.assertIn('%{buildroot}/usr/lib/systemd/system-preset/80-aurora-image.preset', text)
    def test_system_fixes_install_the_desktop_drop_ins(self):
        d = ROOT / 'packages' / 'aurora-release'
        text = (d / 'aurora-release.spec').read_text()
        files = text.split('%files -n aurora-system-fixes', 1)[1].split('%changelog', 1)[0]
        for source, target in (('drkonqi-ordering.conf', '%{buildroot}%{_userunitdir}/$unit.d/50-aurora-ordering.conf'),
                               ('nm-dispatcher-persist.conf', '%{buildroot}%{_unitdir}/NetworkManager-dispatcher.service.d/50-aurora-persist.conf'),
                               ('plasma-setup-xdg-autostart.conf', '%{buildroot}%{_tmpfilesdir}/plasma-setup-xdg-autostart.conf')):
            self.assertRegex(text, rf'(?m)^Source\d+: {re.escape(source)}$')
            self.assertIn(target, text)
        self.assertIn('for unit in drkonqi-coredump-cleanup.timer drkonqi-sentry-postman.path; do', text)
        for path in ('%{_userunitdir}/drkonqi-*.d/50-aurora-ordering.conf',
                     '%{_unitdir}/NetworkManager-dispatcher.service.d/50-aurora-persist.conf',
                     '%{_tmpfilesdir}/plasma-setup-xdg-autostart.conf'):
            self.assertIn(path, files)

    def test_drkonqi_units_keep_shutdown_ordering_only(self):
        # KDE bug 528003: the units order themselves after the targets their
        # default dependencies put them before.
        unit = configparser.ConfigParser(strict=False)
        unit.optionxform = str
        unit.read_string((ROOT / 'packages/aurora-release/drkonqi-ordering.conf').read_text())
        self.assertEqual(dict(unit['Unit']), {'DefaultDependencies': 'no', 'Conflicts': 'shutdown.target',
                                              'Before': 'shutdown.target'})

    def test_nm_dispatcher_persists_until_networkmanager_stops(self):
        lines = [line for line in (ROOT / 'packages/aurora-release/nm-dispatcher-persist.conf').read_text().splitlines()
                 if line and not line.startswith('#')]
        # Fedora installs the dispatcher in libexec.
        self.assertEqual(lines, ['[Unit]', 'Before=NetworkManager.service', '[Service]', 'ExecStart=',
                                 'ExecStart=/usr/libexec/nm-dispatcher --persist'])

    def test_plasma_setup_autostart_entry_is_not_executable(self):
        # Mode adjustments run in file name order: the fix must follow
        # plasma-setup's own recursive 0750.
        fix = ROOT / 'packages/aurora-release/plasma-setup-xdg-autostart.conf'
        self.assertGreater(fix.name, 'plasma-setup-tmpfiles.conf')
        tmpfiles = shutil.which('systemd-tmpfiles')
        if not tmpfiles:
            self.skipTest('systemd-tmpfiles is not installed')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'usr/share/plasma-setup').mkdir(parents=True)
            (root / 'usr/share/plasma-setup/plasma-setup.desktop').write_text('[Desktop Entry]\n')
            (root / 'usr/share/plasma-setup/plasma-setup.desktop').chmod(0o644)
            config = root / 'usr/lib/tmpfiles.d'
            config.mkdir(parents=True)
            # plasma-setup 6.8.2's lines; ownership is left out so that this
            # runs unprivileged.
            (config / 'plasma-setup-tmpfiles.conf').write_text(
                'd /run/plasma-setup - - - - -\n'
                'C /run/plasma-setup/.config/autostart/plasma-setup.desktop - - - - '
                '/usr/share/plasma-setup/plasma-setup.desktop\n'
                'Z /run/plasma-setup 0750 - - - -\n')
            (config / fix.name).write_bytes(fix.read_bytes())
            (root / 'run').mkdir()
            result = subprocess.run([tmpfiles, f'--root={root}', '--create'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            entry = root / 'run/plasma-setup/.config/autostart/plasma-setup.desktop'
            self.assertEqual(entry.stat().st_mode & 0o777, 0o640)
            self.assertEqual((root / 'run/plasma-setup').stat().st_mode & 0o777, 0o750)

    def test_remix_scripts_ship_no_first_boot_units(self):
        d = ROOT / 'packages' / 'aurora-remix-scripts'
        text = (d / 'aurora-remix-scripts.spec').read_text()
        files = text.split('%files', 1)[1].split('%changelog', 1)[0]
        self.assertNotIn('asahi-', files)
        self.assertFalse(list(d.glob('*.service')))
    def test_firstboot_package_ships_the_growfs_gate(self):
        text = (ROOT / 'packages' / 'aurora-firstboot' / 'aurora-firstboot.spec').read_text()
        files = text.split('%files', 1)[1].split('%changelog', 1)[0]
        for unit in ('systemd-growfs-root.service', 'systemd-growfs@.service'):
            self.assertIn(f'%{{_unitdir}}/{unit}.d/aurora-growfs.conf', files)
        self.assertIn('/usr/lib/aurora/\n', files)
    def test_secboot_subpackage_ships_the_uki_pipeline(self):
        text = (ROOT / 'packages' / 'aurora-firstboot' / 'aurora-firstboot.spec').read_text()
        sub = text.split('%package -n aurora-secboot', 1)[1].split('%description', 1)[0]
        for tool in ('systemd-ukify', 'systemd-boot-unsigned', 'sbsigntools', 'openssl', 'python3'):
            self.assertRegex(sub, rf'(?m)^Requires: .*\b{tool}\b')
        self.assertIn('make install-secboot install-selinux-secboot', text)
        self.assertIn('selinux/aurora_secboot.pp', text.split('%build', 1)[1].split('%install', 1)[0])
        files = text.split('%files -n aurora-secboot', 1)[1].split('%changelog', 1)[0]
        for path in ('%{_bindir}/aurora-secboot', '%{_prefix}/lib/kernel/install.d/92-aurora-secboot.install',
                     '%{_unitdir}/aurora-secboot-adopt.service', '%config(noreplace) %{_sysconfdir}/aurora/secboot.conf',
                     '%dir %attr(0700,root,root) %{_sharedstatedir}/aurora/secboot',
                     '%{_datadir}/selinux/packages/%{selinuxtype}/aurora_secboot.pp'):
            self.assertIn(path, files)
        # Fedora builds with dracut; the mkinitcpio hook belongs to ALARM.
        self.assertNotIn('initcpio', text)
        post = text.split('%post -n aurora-secboot', 1)[1].split('%preun', 1)[0]
        self.assertIn('%selinux_modules_install', post)
        self.assertIn('restorecon -R %{_sharedstatedir}/aurora/secboot',
                      text.split('%posttrans -n aurora-secboot', 1)[1].split('%post', 1)[0])
        for lab in ('debug_shell', 'panic=', 'watchdog_sec'):
            self.assertNotIn(lab, text)
    def test_reboot_watchdog_fits_the_apple_hardware_watchdog(self):
        # The Apple SoC watchdog (24 MHz, 32-bit) cannot time out later than
        # about 178 s; a longer RebootWatchdogSec makes the kernel feed it, so
        # a stalled reboot is not reset. Both values must stay within range.
        d = ROOT / 'packages' / 'aurora-platform'
        conf = (d / '90-aurora-reboot-watchdog.conf').read_text()
        values = dict(re.findall(r'(?m)^(\w+WatchdogSec)=(\S+)$', conf))
        self.assertEqual(values, {'RebootWatchdogSec': '2min', 'KExecWatchdogSec': '2min'})
        self.assertIn('[Manager]', conf.splitlines())
        hw_max_s = (2**32 - 1) // 24_000_000
        for value in values.values():
            seconds = int(value[:-3]) * 60
            self.assertGreater(seconds, 0)
            self.assertLessEqual(seconds, hw_max_s)
        text = (d / 'aurora-platform.spec').read_text()
        self.assertRegex(text, r'(?m)^Source\d+: 90-aurora-reboot-watchdog\.conf$')
        install = text.split('%install', 1)[1].split('%posttrans core', 1)[0]
        self.assertIn('%{buildroot}%{_prefix}/lib/systemd/system.conf.d/90-aurora-reboot-watchdog.conf', install)
        core_files = text.split('%files core', 1)[1].split('%files selinux', 1)[0]
        self.assertIn('%{_prefix}/lib/systemd/system.conf.d/90-aurora-reboot-watchdog.conf\n', core_files)
    def test_initramfs_carries_the_usb4_router_with_the_type_c_controllers(self):
        # dracut-asahi brings tps6598x and sn201202x; their router must come too.
        d = ROOT / 'packages' / 'aurora-platform'
        setup = (d / 'usb4-module-setup.sh').read_text()
        self.assertRegex(setup, r"(?m)^\s+hostonly='' instmods thunderbolt_apple$")
        text = (d / 'aurora-platform.spec').read_text()
        self.assertRegex(text, r'(?m)^Source\d+: usb4-module-setup\.sh$')
        self.assertIn('/lib/dracut/modules.d/91aurora-usb4/module-setup.sh', text)
        core_files = text.split('%files core', 1)[1].split('%changelog', 1)[0]
        self.assertIn('%{_prefix}/lib/dracut/modules.d/91aurora-usb4/', core_files)
        config = (ROOT / 'packages' / 'kernel-aurora' / 'config').read_text()
        self.assertIn('CONFIG_USB4_APPLE_SOC=m', config.splitlines())
    def test_initramfs_coldplugs_the_display_first(self):
        # F45's initramfs pivots before udev reaches the display; a pre-trigger
        # hook queues it (and its suppliers) ahead of systemd-udev-trigger.
        d = ROOT / 'packages' / 'aurora-platform'
        setup = (d / 'early-kms-module-setup.sh').read_text()
        self.assertRegex(setup, r"(?m)^\s+hostonly='' instmods appledrm ")
        # appledrm waits for every DCP: an external DCP's Type-C chain comes up with it.
        for module in ('i2c-pasemi-platform', 'phy-apple-atc', 'phy-ti-cd2e22', 'tps6598x'):
            self.assertIn(module, setup.split('installkernel()', 1)[1].split('}', 1)[0])
        self.assertRegex(setup, r'(?m)^\s+inst_hook pre-trigger \d+ "\$moddir/aurora-early-kms\.sh"$')
        hook = (d / 'aurora-early-kms.sh').read_text()
        self.assertIn("*Capple,display-subsystem*|*Capple,dcp*)", hook)
        self.assertIn('*Capple,*atcphy*|*Capple,*-i2cC*|*Capple,i2c)', hook)
        self.assertIn('supplier:*', hook)
        self.assertIn('udevadm trigger --action=add --subsystem-match=drm', hook)
        # It queues the display ahead of the coldplug but never waits for it:
        # appledrm comes up only once every DCP has started.
        self.assertNotIn('--settle', hook)
        self.assertNotIn('udevadm settle', hook)
        self.assertNotRegex(hook, r'(?m)^\s*modprobe ')
        subprocess.run(['sh', '-n', str(d / 'aurora-early-kms.sh')], check=True)
        text = (d / 'aurora-platform.spec').read_text()
        self.assertRegex(text, r'(?m)^Source\d+: early-kms-module-setup\.sh$')
        self.assertRegex(text, r'(?m)^Source\d+: aurora-early-kms\.sh$')
        self.assertIn('/lib/dracut/modules.d/91aurora-early-kms/module-setup.sh', text)
        self.assertIn('/lib/dracut/modules.d/91aurora-early-kms/aurora-early-kms.sh', text)
        core_files = text.split('%files core', 1)[1].split('%changelog', 1)[0]
        self.assertIn('%{_prefix}/lib/dracut/modules.d/91aurora-early-kms/', core_files)
    def test_kdump_crash_kernel_initramfs_has_the_disk_and_a_clock(self):
        # kdump-utils' 99-kdump.conf replaces add_dracutmodules, so the Aurora
        # conf must sort after it and name nvme_apple itself.
        d = ROOT / 'packages' / 'aurora-platform'
        conf = (d / 'aurora-kdump-dracut.conf').read_text()
        self.assertRegex(conf, r'(?m)^add_drivers\+=" nvme_apple "$')
        self.assertRegex(conf, r'(?m)^add_dracutmodules\+=" aurora-kdump-clock "$')
        self.assertGreater('99-zz-aurora.conf', '99-kdump.conf')
        setup = (d / 'aurora-kdump-clock-module-setup.sh').read_text()
        self.assertRegex(setup, r'(?m)^\s+return 255$')
        self.assertRegex(setup, r'(?m)^\s+inst_hook pre-mount \d+ "\$moddir/aurora-kdump-clock\.sh"$')
        hook = (d / 'aurora-kdump-clock.sh').read_text()
        self.assertIn('[ ! -e /dev/rtc0 ]', hook)
        self.assertIn('CRASHTIME', hook)
        self.assertIn('hwclock --hctosys --utc -f "$_rtc"', hook)
        self.assertNotRegex(hook, r'(?m)^\s*exit\b')  # sourced by dracut
        self.assertRegex(setup, r'(?m)^\s+inst_multiple hwclock head tr sed date$')
        # The crash kernel must not load drivers of live coprocessors.
        omit = re.search(r'(?m)^omit_drivers\+="([^"]*)"$', conf)
        self.assertIsNotNone(omit)
        for drv in ('aurora', 'appledrm', 'thunderbolt', 'apple[-_]pmp', 'aop', 'i2c[-_]pasemi.*', 'xhci.*'):
            self.assertIn(drv, omit.group(1).split())
        self.assertNotIn('nvme', omit.group(1))
        # No squashfs image behind a busybox /init in the crash kernel.
        squash = re.search(r'(?m)^omit_dracutmodules\+="([^"]*)"$', conf)
        self.assertIsNotNone(squash)
        for mod in ('squash', 'squash-squashfs', 'squash-lib'):
            self.assertIn(mod, squash.group(1).split())
        # The hook takes CRASHTIME from a vmcoreinfo-like stream.
        vmcore = b'\x7fELF\x00\x01OSRELEASE=7.3.0\nCRASHTIME=1794139056\n\x00\x02'
        out = subprocess.run(['sh', '-c', "tr -c '[:print:]' '\\n' | sed -n 's/^CRASHTIME=\\([0-9][0-9]*\\)$/\\1/p' | head -n 1"],
                             input=vmcore, capture_output=True, check=True).stdout
        self.assertEqual(out, b'1794139056\n')
        for script in ('aurora-kdump-clock.sh', 'aurora-kdump-setup'):
            subprocess.run(['sh', '-n', str(d / script)], check=True)
        unit = (d / 'aurora-kdump.service.conf').read_text()
        self.assertIn("ExecCondition=/bin/sh -c 'test \"$(cat /sys/kernel/kexec_crash_size)\" -gt 0'", unit)

    def test_kdump_is_an_opt_in_subpackage(self):
        text = (ROOT / 'packages' / 'aurora-platform' / 'aurora-platform.spec').read_text()
        main_and_core = text.split('%package kdump', 1)[0]
        self.assertNotRegex(main_and_core, r'(?m)^Requires:.*kdump')
        self.assertNotIn('kdump', text.split('%posttrans core', 1)[1].split('%files', 1)[0].split('%post kdump', 1)[0])
        self.assertFalse((ROOT / 'packages' / 'aurora-platform' / '80-aurora-kdump.preset').exists())
        self.assertNotIn('kdump', text.split('%files core', 1)[1].split('%files', 1)[0])
        self.assertRegex(text, r'(?m)^Requires: kdump-utils makedumpfile grubby$')
        self.assertIn('if [ "$1" -eq 1 ]; then\n  %{_libexecdir}/aurora/aurora-kdump-setup enable || :',
                      text.split('%post kdump', 1)[1].split('%preun kdump', 1)[0])
        self.assertIn('if [ "$1" -eq 0 ]; then\n  %{_libexecdir}/aurora/aurora-kdump-setup disable || :',
                      text.split('%preun kdump', 1)[1].split('%pre selinux', 1)[0])
        kdump_files = text.split('%files kdump', 1)[1].split('%files selinux', 1)[0]
        for path in ('%{_prefix}/lib/kdump/dracut.conf.d/99-zz-aurora.conf',
                     '%{_prefix}/lib/dracut/modules.d/99aurora-kdump-clock/',
                     '%{_unitdir}/kdump.service.d/50-aurora-kdump.conf',
                     '%{_libexecdir}/aurora/aurora-kdump-setup'):
            self.assertIn(path + '\n', kdump_files)

    def test_kdump_setup_enables_and_undoes_only_what_it_added(self):
        script = ROOT / 'packages' / 'aurora-platform' / 'aurora-kdump-setup'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / 'bin'
            bindir.mkdir()
            log = root / 'calls'
            for tool in ('systemctl', 'grubby'):
                (bindir / tool).write_text(f'#!/bin/sh\necho {tool} "$@" >> "{log}"\n')
                (bindir / tool).chmod(0o755)
            cmdline, state = root / 'cmdline', root / 'state' / 'kdump-crashkernel-added'
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", AURORA_KDUMP_STATE=str(state),
                       AURORA_KERNEL_CMDLINE=str(cmdline))
            run = lambda *a: subprocess.run(['sh', str(script), *a], env=env, capture_output=True, text=True)
            # An owner's crashkernel= is kept on enable and on disable.
            cmdline.write_text('root=UUID=x ro crashkernel=512M\n')
            self.assertEqual(run('enable').returncode, 0)
            self.assertEqual(log.read_text(), 'systemctl enable --quiet kdump.service\n')
            self.assertFalse(state.exists())
            log.write_text('')
            run('disable')
            self.assertEqual(log.read_text(), 'systemctl disable --quiet kdump.service\n')
            self.assertEqual(cmdline.read_text(), 'root=UUID=x ro crashkernel=512M\n')
            # Without one, enable sets kdump-utils' default and disable removes it.
            log.write_text('')
            cmdline.write_text('root=UUID=x ro\n')
            run('enable')
            self.assertEqual(log.read_text(), 'systemctl enable --quiet kdump.service\ngrubby --update-kernel=ALL --args=crashkernel=512M\n')
            self.assertEqual(cmdline.read_text(), 'root=UUID=x ro crashkernel=512M\n')
            self.assertTrue(state.exists())
            cmdline.write_text('root=UUID=x ro crashkernel=512M quiet\n')
            log.write_text('')
            run('disable')
            self.assertEqual(log.read_text(), 'systemctl disable --quiet kdump.service\ngrubby --update-kernel=ALL --remove-args=crashkernel\n')
            self.assertEqual(cmdline.read_text(), 'root=UUID=x ro quiet\n')
            self.assertFalse(state.exists())
            self.assertEqual(run().returncode, 2)
            # A failed enable or disable is reported, not hidden; the rest still runs.
            for tool in ('systemctl', 'grubby'):
                (bindir / tool).write_text(f'#!/bin/sh\necho {tool} "$@" >> "{log}"\nexit 1\n')
            cmdline.write_text('root=UUID=x ro\n')
            result = run('enable')
            self.assertEqual(result.returncode, 0)
            self.assertIn('could not enable kdump.service', result.stderr)
            self.assertIn('grubby failed', result.stderr)
            state.parent.mkdir(exist_ok=True)
            state.touch()
            result = run('disable')
            self.assertIn('could not disable kdump.service', result.stderr)
            self.assertIn('grubby failed; remove crashkernel=', result.stderr)

    def test_grub_uuid_refresh_replaces_only_stale_uuid_searches(self):
        script = ROOT / 'packages' / 'aurora-platform' / 'aurora-grub-uuid'
        spec = (ROOT / 'packages' / 'aurora-platform' / 'aurora-platform.spec').read_text()
        self.assertIn('%{_libexecdir}/aurora/aurora-grub-uuid || :',
                      spec.split('%posttrans core', 1)[1].split('%files', 1)[0])
        self.assertIn('%{_libexecdir}/aurora/aurora-grub-uuid\n', spec.split('%files core', 1)[1])
        fresh = ('insmod fat\nsearch --no-floppy --fs-uuid --set=root 81f0fc7d-1e2c\n'
                 'search --no-floppy --fs-uuid --set=boot 8790-1917\ninsmod blscfg\n')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bindir = root / 'bin'
            bindir.mkdir()
            (root / 'generated').write_text(fresh)
            # Fails unless the BLS entries are left alone (--no-grubenv-update).
            (bindir / 'grub2-mkconfig').write_text(
                f'#!/bin/sh\ncase " $* " in *" --no-grubenv-update "*) ;; *) exit 9;; esac\ncat {root / "generated"}\n')
            (bindir / 'grub2-mkconfig').chmod(0o755)
            cfg = root / 'grub.cfg'
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", AURORA_GRUB_CFG=str(cfg))
            run = lambda: subprocess.run(['sh', str(script)], env=env, check=True)
            # Only the ESP UUID search is stale: regenerate, keeping a backup.
            stale = fresh.replace('8790-1917', '6ADB-FEED')
            cfg.write_text(stale)
            run()
            self.assertEqual(cfg.read_text(), fresh)
            self.assertEqual((root / 'grub.cfg.aurora-uuid').read_text(), stale)
            # Any other difference, an added line included, leaves grub.cfg alone.
            for custom in (stale.replace('insmod blscfg', 'insmod blscfg\nset timeout=5'),
                           stale.replace('insmod fat', 'insmod ext2'),
                           fresh.replace('--set=boot 8790-1917', '--set=boot 8790-1917 --hint x')):
                cfg.write_text(custom)
                run()
                self.assertEqual(cfg.read_text(), custom)
            # Up to date: nothing to do.
            cfg.write_text(fresh)
            run()
            self.assertEqual(cfg.read_text(), fresh)

    def test_grub_console_migration_runs_once_and_keeps_hand_made_configs(self):
        script = ROOT / 'packages' / 'aurora-platform' / 'aurora-grub-console'
        spec = (ROOT / 'packages' / 'aurora-platform' / 'aurora-platform.spec').read_text()
        self.assertIn('%{_libexecdir}/aurora/aurora-grub-console || :',
                      spec.split('%posttrans core', 1)[1].split('%files', 1)[0])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bindir = root / 'bin'
            bindir.mkdir()
            # A stand-in grub2-mkconfig that renders the terminal setting.
            (bindir / 'grub2-mkconfig').write_text(
                '#!/bin/sh\n. "$AURORA_GRUB_DEFAULTS"\n'
                'case " $* " in *" --no-grubenv-update "*) ;; *) echo "BLS entries rewritten" >&2; exit 9;; esac\n'
                'out="terminal_output $GRUB_TERMINAL_OUTPUT"\n'
                'if [ "${1:-}" = -o ]; then echo "$out" > "$2"; else echo "$out"; fi\n')
            (bindir / 'grub2-mkconfig').chmod(0o755)
            conf, cfg, state = root / 'grub', root / 'grub.cfg', root / 'state' / 'applied'
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", AURORA_GRUB_DEFAULTS=str(conf),
                       AURORA_GRUB_CFG=str(cfg), AURORA_GRUB_STATE=str(state))
            run = lambda: subprocess.run(['sh', str(script)], env=env, check=True, capture_output=True, text=True)
            # A hand-maintained grub.cfg is left alone, and the migration stays pending.
            conf.write_text('GRUB_TIMEOUT=5\nGRUB_TERMINAL_OUTPUT="gfxterm"\n')
            cfg.write_text('custom\n')
            self.assertIn('leaving GRUB_TERMINAL_OUTPUT=gfxterm', run().stderr)
            self.assertIn('GRUB_TERMINAL_OUTPUT="gfxterm"', conf.read_text())
            self.assertEqual(cfg.read_text(), 'custom\n')
            self.assertFalse(state.exists())
            # A generated grub.cfg: switch to the console and regenerate, once.
            cfg.write_text('terminal_output gfxterm\n')
            run()
            self.assertIn('GRUB_TERMINAL_OUTPUT="console"\n', conf.read_text())
            self.assertIn('GRUB_TIMEOUT=5\n', conf.read_text())
            self.assertEqual(cfg.read_text(), 'terminal_output console\n')
            self.assertTrue(state.exists())
            # The owner chooses gfxterm again: it stays.
            conf.write_text('GRUB_TERMINAL_OUTPUT="gfxterm"\n')
            run()
            self.assertEqual(conf.read_text(), 'GRUB_TERMINAL_OUTPUT="gfxterm"\n')
    def test_aura_ships_both_stage1_forms_from_the_stage1_build(self):
        spec = (ROOT / 'packages' / 'aura' / 'aura.spec').read_text()
        # Both come from the Stage 1 build, before `make clean` rebuilds for Stage 2.
        stage1 = spec.split('%build', 1)[1].split('make clean', 1)[0]
        self.assertIn('cp build/aura.bin ../aurora-stage1/aura-raw.bin\n', stage1)
        self.assertIn('cp build/aura-boot.macho ../aurora-stage1/aura-boot.macho\n', stage1)
        for name in ('aura-raw.bin', 'aura-boot.macho'):
            self.assertIn(f'install -Dm644 ../aurora-stage1/{name} %{{buildroot}}%{{_datadir}}/aura/stage1/{name}\n', spec)
    def test_aura_ships_a_secure_stage1_with_a_throwaway_key(self):
        spec = (ROOT / 'packages' / 'aura' / 'aura.spec').read_text()
        build = spec.split('%build', 1)[1].split('%install', 1)[0]
        # The second `make clean` starts the secure-flavour Stage 1, the third the Stage 2 build.
        secure = build.split('make clean', 2)[1]
        self.assertIn('secboot_sign.pubkey(os.urandom(32))', secure)
        self.assertIn('SECBOOT=audit SECBOOT_FLAVOUR=secure SECBOOT_PUBKEY=../aurora-stage1/nobody.pub', secure)
        self.assertIn('cp build/aura.bin ../aurora-stage1/aura-secure-raw.bin\n', secure)
        self.assertIn('cp build/aura-boot.macho ../aurora-stage1/aura-secure-boot.macho\n', secure)
        self.assertIn('install -Dm644 ../aurora-stage1/aura-secure-boot.macho '
                      '%{buildroot}%{_datadir}/aura/stage1/aura-secure-boot.macho\n', spec)
        self.assertIn('ESP_STAGE2=1', build.split('make clean', 2)[2])
        install = spec.split('%install', 1)[1].split('%files', 1)[0]
        self.assertIn('install -Dm644 ../aurora-stage1/aura-secure-raw.bin '
                      '%{buildroot}%{_datadir}/aura/stage1/aura-secure-raw.bin\n', install)
        self.assertNotIn('nobody.pub', install)
    def test_fex_guest_mesa_moves_in_lockstep_with_the_host_mesa(self):
        def fields(name):
            text = (ROOT / 'packages' / name / (name + '.spec')).read_text()
            commit = re.search(r'^%(?:\{!\?commit:)?%?global commit ([0-9a-f]{40})', text, re.M).group(1)
            version = re.search(r'^Version:\s+(\S+)', text, re.M).group(1)
            release = re.search(r'^Release:\s+(\S+)', text, re.M).group(1)
            macros = dict(re.findall(r'^%\{!\?(\w+):%global \1 (\S+)\}', text, re.M))
            expand = lambda value: re.sub(r'%\{(\w+)\}', lambda m: macros.get(m.group(1), m.group(0)), value)
            return commit, expand(version), expand(release), text
        host, guest = fields('mesa-aurora'), fields('mesa-aurora-fex-guest')
        self.assertEqual(host[:3], guest[:3])
        sources = json.loads((ROOT / 'sources.json').read_text())
        self.assertEqual(sources['mesa-aurora-fex-guest'], sources['mesa-aurora'])
        self.assertEqual(sources['mesa-aurora']['commit'], host[0])
        self.assertIn('BuildArch: noarch', guest[3])
        self.assertIn('# aurora-builder: x86_64', guest[3].splitlines())
        self.assertIn('Requires: mesa-dri-drivers = %{version}-%{release}', guest[3])
        self.assertIn('Requires: mesa-vulkan-drivers = %{version}-%{release}', guest[3])
    def test_aurora_sep_ships_the_touch_id_reset(self):
        sep = ROOT / 'packages/aurora-sep'
        self.assertRegex((sep / 'aurora-sep.spec').read_text(), r'(?m)^Requires: aurora-xart$')
        xart = (ROOT / 'packages/aurora-xart/aurora-xart.spec').read_text()
        self.assertIn('BuildArch: noarch', xart)
        self.assertIn('make check', xart.split('%check', 1)[1].split('%install', 1)[0])
        self.assertIn('%{_mandir}/man8/aurora-xart.8*', xart)
        # The installer script is not shipped here; the packaged tool is.
        for doc in ('README.md', 'XART-SAFETY.md'):
            text = (sep / doc).read_text()
            self.assertNotIn('install-aurora-sep.sh --reset-touchid', text)
            self.assertIn('aurora-xart reset-touchid', text)
        conf = (ROOT / 'packages/aurora-repos/aurora-vendors-unvendored.conf').read_text()
        self.assertIn("{ filter = 'source_name', value = 'aurora-xart' }", conf)
    def test_spec_commit_matches_its_source_pin(self):
        sources = json.loads((ROOT / 'sources.json').read_text())
        for spec in (ROOT / 'packages').glob('*/*.spec'):
            name = spec.parent.name
            match = re.search(r'^%(?:\{!\?commit:)?%?global commit ([0-9a-f]{40})', spec.read_text(), re.M)
            if name not in sources or not match:
                continue
            with self.subTest(package=name):
                self.assertEqual(sources[name]['commit'], match.group(1))
    def test_flatpak_gl_moves_in_lockstep_with_the_host_mesa(self):
        def fields(name):
            text = (ROOT / 'packages' / name / (name + '.spec')).read_text()
            commit = re.search(r'^%(?:\{!\?commit:)?%?global commit ([0-9a-f]{40})', text, re.M).group(1)
            macros = dict(re.findall(r'^%\{!\?(\w+):%global \1 (\S+)\}', text, re.M))
            expand = lambda value: re.sub(r'%\{(\w+)\}', lambda m: macros.get(m.group(1), m.group(0)), value)
            version = expand(re.search(r'^Version:\s+(\S+)', text, re.M).group(1))
            release = expand(re.search(r'^Release:\s+(\S+)', text, re.M).group(1))
            return commit, version, release, text
        host, gl = fields('mesa-aurora'), fields('aurora-flatpak-gl')
        self.assertEqual(host[:3], gl[:3])
        self.assertEqual(json.loads((ROOT / 'sources.json').read_text())['mesa-aurora']['commit'], gl[0])
        self.assertIn('aurora-mesa-commit.', gl[3])
        self.assertIn('aurora-mesa-commit.', (ROOT / 'packages' / 'aurora-flatpak-gl' / 'build-extension.sh').read_text())
    def test_fedora45_graphics_are_pinned_and_versioned_together(self):
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        import fedoralib
        host = fedoralib.recipe_files(ROOT, 'mesa-aurora', 45)['mesa-aurora.spec'].read_text()
        pin = fedoralib.sources(ROOT, 45)['mesa-aurora']
        self.assertEqual(pin, fedoralib.sources(ROOT, 44)['mesa-aurora'])
        self.assertIn('%global commit ' + pin['commit'], host)
        self.assertRegex(host, r'(?m)^Epoch: 1$')
        f44 = fedoralib.recipe_files(ROOT, 'mesa-aurora', 44)['mesa-aurora.spec'].read_text()
        release = re.search(r'(?m)^Release: (\d+)%\{\?dist\}\.aurora$', f44).group(1)
        self.assertRegex(host, r'(?m)^Release: ' + release + r'%\{\?dist\}.aurora$')
        for name in ('mesa-aurora-fex-guest', 'aurora-flatpak-gl'):
            text = fedoralib.recipe_files(ROOT, name, 45)[name + '.spec'].read_text()
            self.assertIn('%global commit ' + pin['commit'], text)
            self.assertIn('%global host_release ' + release + '%{?dist}.aurora', text)
        guest = fedoralib.recipe_files(ROOT, 'mesa-aurora-fex-guest', 45)['mesa-aurora-fex-guest.spec'].read_text()
        self.assertIn('Requires: mesa-dri-drivers = %{epoch}:%{version}-%{release}', guest)
        self.assertIn('Requires: mesa-vulkan-drivers = %{epoch}:%{version}-%{release}', guest)

    def test_flatpak_gl_settings_name_the_files_the_extension_ships(self):
        d = ROOT / 'packages' / 'aurora-flatpak-gl'
        helper = (d / 'aurora-flatpak-gl').read_text()
        manifest = (d / 'org.freedesktop.Platform.GL.aurora.yml.in').read_text()
        build = (d / 'build-extension.sh').read_text()
        # The override points at the merged GL directories; the extension must
        # ship files under the same names, at the merge-dirs locations.
        for name in ['vulkan/icd.d/asahi_icd.aarch64.json', 'vulkan/icd.d/lvp_icd.aarch64.json',
                     'glvnd/egl_vendor.d/50_mesa.json', 'lib/dri']:
            self.assertIn('$gl/' + name, helper)
        self.assertIn('-Dvulkan-drivers=asahi,swrast', manifest)
        self.assertIn('mv ${FLATPAK_DEST}/share/vulkan/icd.d ${FLATPAK_DEST}/vulkan/icd.d', manifest)
        self.assertIn('mv ${FLATPAK_DEST}/share/glvnd/egl_vendor.d ${FLATPAK_DEST}/glvnd/egl_vendor.d', manifest)
        self.assertIn("prefix: /usr/lib/aarch64-linux-gnu/GL/aurora", manifest)
        self.assertIn('priority=10', build)
        self.assertIn("['mesa-aurora']", build)
    def test_platform_selinux_lets_initramfs_plymouth_map_a_fresh_drm_card(self):
        # A /dev/dri/cardN made after the policy load is xserver_misc_device_t
        # until udev relabels it; plymouthd from the initramfs is kernel_t.
        # Only the map is added: nothing wider, no other source or target.
        te = (ROOT / 'packages' / 'aurora-platform' / 'aurora_platform.te').read_text()
        rules = [r for r in re.findall(r'(?m)^allow .*$', te) if 'xserver_misc_device_t' in r]
        self.assertEqual(rules, ['allow kernel_t xserver_misc_device_t:chr_file map;'])
        self.assertRegex(te, r'(?m)^\ttype init_t, kernel_t, xserver_misc_device_t;$')
        self.assertRegex(te, r'(?m)^\tclass chr_file map;$')
    def test_platform_selinux_lets_init_inspect_the_initramfs_uevent_socket(self):
        # systemd keeps udev's uevent socket from the initramfs, where it was
        # made as kernel_t, and checks it after loading the policy.
        d = ROOT / 'packages' / 'aurora-platform'
        te = (d / 'aurora_platform.te').read_text()
        self.assertIn('allow init_t kernel_t:netlink_kobject_uevent_socket getattr;', te)
        self.assertEqual(re.findall(r'(?m)^allow .*$', te),
                         ['allow init_t kernel_t:netlink_kobject_uevent_socket getattr;',
                          'allow kernel_t xserver_misc_device_t:chr_file map;'])
        text = (d / 'aurora-platform.spec').read_text()
        self.assertRegex(text, r'(?m)^Source\d+: aurora_platform\.te$')
        core = text.split('%package core', 1)[1].split('%description core', 1)[0]
        self.assertIn('Requires: (aurora-platform-selinux = %{version}-%{release} '
                      'if selinux-policy-%{selinuxtype})', core)
        files = text.split('%files selinux', 1)[1].split('%changelog', 1)[0]
        self.assertIn('%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2', files)
    def test_platform_selinux_silences_the_gdm_keyring_scan_only(self):
        # pam_gdm reads /proc/keys looking for the cryptsetup passphrase; the
        # regulatory certificate keys it may not view are skipped. Nothing is
        # allowed: one dontaudit, xdm_t on unconfined_service_t keys, view only.
        te = (ROOT / 'packages' / 'aurora-platform' / 'aurora_platform.te').read_text()
        self.assertEqual(re.findall(r'(?m)^dontaudit .*$', te),
                         ['dontaudit xdm_t unconfined_service_t:key view;'])
        self.assertEqual([r for r in re.findall(r'(?m)^allow .*$', te) if ':key ' in r], [])
        self.assertRegex(te, r'(?m)^\ttype xdm_t, unconfined_service_t;$')
        self.assertRegex(te, r'(?m)^\tclass key view;$')
    def test_irqbalance_runs_only_where_the_aic_can_steer(self):
        d = ROOT / 'packages' / 'aurora-platform'
        conf = (d / '50-aurora-irqbalance.conf').read_text()
        # Keyed on the interrupt controller's compatible, not on a SoC.
        self.assertEqual([l for l in conf.splitlines() if l and not l.startswith('#')],
                         ['[Service]', 'ExecCondition=/usr/libexec/aurora/aurora-irq-steerable'])
        script = d / 'aurora-irq-steerable'
        subprocess.run(['sh', '-n', str(script)], check=True)
        def run(root_compat, aic_compat):
            with tempfile.TemporaryDirectory() as tmp:
                # Like /proc/device-tree, the tree is reached through a symlink.
                dt = Path(tmp) / 'base'
                dt.mkdir()
                (Path(tmp) / 'device-tree').symlink_to(dt)
                (dt / 'compatible').write_bytes(root_compat)
                if aic_compat is not None:
                    node = dt / 'soc' / 'interrupt-controller@23b100000'
                    node.mkdir(parents=True)
                    (node / 'compatible').write_bytes(aic_compat)
                text = script.read_text().replace('dt=/proc/device-tree', f'dt={tmp}/device-tree')
                return subprocess.run(['sh', '-c', text]).returncode
        self.assertEqual(run(b'apple,j293\0apple,t8103\0apple,arm-platform\0', b'apple,t8103-aic\0apple,aic\0'), 0)
        self.assertEqual(run(b'apple,j316s\0apple,t6000\0apple,arm-platform\0', b'apple,t6000-aic\0apple,aic2\0'), 1)
        self.assertEqual(run(b'apple,j700\0apple,t8140\0apple,arm-platform\0', b'apple,t8140-aic3\0apple,t8122-aic3\0'), 1)
        self.assertEqual(run(b'radxa,rock-5b\0rockchip,rk3588\0', None), 0)
        text = (d / 'aurora-platform.spec').read_text()
        core_files = text.split('%files core', 1)[1].split('%files selinux', 1)[0]
        self.assertIn('%{_unitdir}/irqbalance.service.d/50-aurora-irqbalance.conf', core_files)
    def test_mutter_leaves_the_render_only_gpu_card_alone(self):
        d = ROOT / 'packages' / 'aurora-platform'
        rules = [l for l in (d / '62-aurora-gpu-render-only.rules').read_text().splitlines()
                 if l and not l.startswith('#')]
        self.assertEqual(rules, ['SUBSYSTEM=="drm", KERNEL=="card[0-9]*", DRIVERS=="aurora", '
                                 'TAG+="mutter-device-ignore"'])
        text = (d / 'aurora-platform.spec').read_text()
        core_files = text.split('%files core', 1)[1].split('%files selinux', 1)[0]
        self.assertIn('%{_udevrulesdir}/62-aurora-gpu-render-only.rules', core_files)
    def test_host_clicks_only_where_an_actuator_is(self):
        # macOS plays every click from the host; only MTP trackpads with an
        # actuator node switch, so SPI and external trackpads keep theirs.
        d = ROOT / 'packages' / 'aurora-platform'
        rules = [l for l in (d / '64-aurora-trackpad-clicks.rules').read_text().splitlines()
                 if l and not l.startswith('#')]
        self.assertEqual(rules, ['ACTION=="add|bind", SUBSYSTEM=="hid", DRIVER=="magicmouse", '
                                 'ENV{HID_NAME}=="Apple MTP multi-touch", TEST=="../of_node/actuator", '
                                 'ATTR{[module/hid_magicmouse]parameters/haptic_press}="Y"'])
        text = (d / 'aurora-platform.spec').read_text()
        self.assertRegex(text, r'(?m)^Source\d+: 64-aurora-trackpad-clicks\.rules$')
        core_files = text.split('%files core', 1)[1].split('%files selinux', 1)[0]
        self.assertIn('%{_udevrulesdir}/64-aurora-trackpad-clicks.rules', core_files)
    def test_t6041_trackpads_take_palms_from_the_kernel(self):
        # hid-magicmouse reports T6041 palms as MT_TOOL_PALM; libinput's
        # Apple MTP size threshold is off on those two MacBook Pros only.
        d = ROOT / 'packages' / 'aurora-platform'
        quirks = configparser.ConfigParser(interpolation=None)
        quirks.optionxform = str
        quirks.read_string((d / '60-aurora-t6041-trackpad.quirks').read_text())
        self.assertEqual(sorted(quirks[s]['MatchDeviceTree'] for s in quirks.sections()),
                         ['*j614c*', '*j616c*'])
        for section in quirks.sections():
            with self.subTest(section=section):
                self.assertEqual(dict(quirks[section]), {
                    'MatchUdevType': 'touchpad', 'MatchName': 'Apple*MTP*', 'MatchVendor': '0x05AC',
                    'MatchDeviceTree': quirks[section]['MatchDeviceTree'], 'AttrPalmSizeThreshold': '0'})
        text = (d / 'aurora-platform.spec').read_text()
        self.assertRegex(text, r'(?m)^Source\d+: 60-aurora-t6041-trackpad\.quirks$')
        core_files = text.split('%files core', 1)[1].split('%files kdump', 1)[0]
        self.assertIn('%{_datadir}/libinput/60-aurora-t6041-trackpad.quirks', core_files)
    def test_power_defaults_apply_on_every_apple_silicon_mac(self):
        # Same unit as ALARM's aurora-system-fixes: neither setting depends on
        # the SoC, so one unit, skipped by ConditionFirmware off Apple silicon.
        d = ROOT / 'packages' / 'aurora-platform'
        self.assertFalse((d / 'aurora-t6041-power.service').exists())
        text = (d / 'aurora-power-defaults.service').read_text()
        unit = configparser.ConfigParser(interpolation=None, strict=False)
        unit.optionxform = str
        unit.read_string(text)
        self.assertEqual(unit['Unit']['ConditionFirmware'], 'device-tree-compatible(apple,arm-platform)')
        # aurora-power-modes takes the values it finds at start as the boot
        # baseline that Balanced restores, so these must be in place first.
        self.assertIn('aurora-power-modes.service', unit['Unit']['Before'].split())
        self.assertIn('sysinit.target', unit['Unit']['Before'].split())
        self.assertEqual(unit['Service']['Type'], 'oneshot')
        self.assertNotIn('Install', unit)
        # "-": a kernel booted with pcie_aspm=off refuses the policy and
        # must still get the sysctl.
        self.assertEqual([l for l in text.splitlines() if l.startswith('ExecStart=')], [
            "ExecStart=-/bin/sh -c 'echo powersupersave > /sys/module/pcie_aspm/parameters/policy'",
            'ExecStart=/usr/sbin/sysctl -q -w kernel.sched_util_clamp_min_rt_default=0'])
        spec = (d / 'aurora-platform.spec').read_text()
        self.assertNotIn('aurora-t6041-power.service', spec.split('%changelog', 1)[0])
        self.assertRegex(spec, r'(?m)^Source\d+: aurora-power-defaults\.service$')
        self.assertIn('ln -s ../aurora-power-defaults.service '
                      '%{buildroot}%{_unitdir}/sysinit.target.wants/aurora-power-defaults.service', spec)
        core_files = spec.split('%files core', 1)[1].split('%files kdump', 1)[0]
        self.assertIn('%{_unitdir}/aurora-power-defaults.service', core_files)
        self.assertIn('%{_unitdir}/sysinit.target.wants/aurora-power-defaults.service', core_files)
    def test_lid_policy_follows_the_active_kernel_sleep_mode(self):
        package = ROOT / 'packages' / 'aurora-m5-platform-config'
        unit = configparser.ConfigParser(interpolation=None)
        unit.optionxform = str
        unit.read_string((package / 'aurora-m5-sleep-policy.service').read_text())
        self.assertNotIn('ConditionFirmware', unit['Unit'])
        self.assertEqual(unit['Service']['Type'], 'oneshot')
        self.assertTrue(unit['Service'].getboolean('RemainAfterExit'))
        self.assertNotIn('ExecCondition', unit['Service'])
        self.assertIn('systemd-logind.service', unit['Unit']['Before'].split())
        self.assertNotIn('Install', unit)
        shell, flags, script = shlex.split(unit['Service']['ExecStart'])
        with tempfile.TemporaryDirectory() as tmp:
            mem_sleep = Path(tmp) / 'mem_sleep'
            dropin = '90-aurora-m5-lid.conf'
            source = package / dropin
            destination = Path(tmp) / 'logind.conf.d' / dropin
            script = script.replace('/sys/power/mem_sleep', shlex.quote(str(mem_sleep)))
            script = script.replace(f'/usr/share/aurora-m5-platform-config/{dropin}',
                                    shlex.quote(str(source)))
            script = script.replace(f'/run/systemd/logind.conf.d/{dropin}',
                                    shlex.quote(str(destination)))
            for modes, installs_policy in (
                ('s2idle [deep]', True),
                ('[s2idle] deep', False),
                ('[s2idle]', False),
                (None, False),
            ):
                with self.subTest(modes=modes):
                    if modes is None:
                        mem_sleep.unlink()
                    else:
                        mem_sleep.write_text(modes + '\n')
                    subprocess.run([shell, flags, script], check=True, timeout=5)
                    self.assertEqual(destination.is_file(), installs_policy)
                    if installs_policy:
                        self.assertEqual(destination.read_bytes(), source.read_bytes())
                        self.assertEqual(destination.stat().st_mode & 0o777, 0o644)
                        destination.unlink()

            mem_sleep.write_text('s2idle [deep]\n')
            destination.parent.rmdir()
            destination.parent.touch()
            failure = subprocess.run([shell, flags, script], capture_output=True, timeout=5)
            self.assertNotEqual(failure.returncode, 0)

        lid = configparser.ConfigParser(interpolation=None)
        lid.optionxform = str
        lid.read_string((package / '90-aurora-m5-lid.conf').read_text())
        self.assertEqual(dict(lid['Login']), {
            'HandleLidSwitch': 'suspend',
            'HandleLidSwitchExternalPower': 'suspend',
            'HandleLidSwitchDocked': 'suspend',
        })
        spec = (package / 'aurora-m5-platform-config.spec').read_text()
        self.assertIn('ln -s ../aurora-m5-sleep-policy.service '
                      '%{buildroot}%{_unitdir}/sysinit.target.wants/aurora-m5-sleep-policy.service', spec)
        self.assertNotIn('/system-sleep/', spec)
        self.assertNotIn('/90-aurora-m5-deep.conf', spec)
        platform = (ROOT / 'packages' / 'aurora-platform' / 'aurora-platform.spec').read_text()
        main = platform.split('%package core', 1)[0]
        self.assertRegex(main, r'(?m)^Requires: .*\baurora-m5-platform-config\b')
    def test_platform_core_carries_no_kernel_or_boot_chain(self):
        d = ROOT / 'packages' / 'aurora-platform'
        text = (d / 'aurora-platform.spec').read_text()
        core = text.split('%package core', 1)[1].split('%description core', 1)[0]
        requires = ' '.join(re.findall(r'^Requires:\s+(.+)$', core, re.M)).split()
        for name in ['update-m1n1', 'aurora-vendor-firmware', 'aurora-firmware-refresh',
                     'aurora-audio', 'alsa-ucm-conf-aurora', 'aurora-camera-denoise',
                     'aurora-kbd-light']:
            self.assertIn(name, requires)
        # speakerguardd v2 is the only speaker stack; aurora-audio 4.1-18 retires
        # speakersafetyd and speakerguardd 0.1.
        self.assertRegex(core, r'(?m)^Requires: speakerguardd-v2 >= 1\.0\.0~alpha\.2-0\.63 aurora-speaker-upgrade >= 0\.1-0\.29$')
        self.assertRegex(core, r'(?m)^Requires: aurora-audio >= 4\.1-18$')
        self.assertNotRegex(core, r'(?m)^(Requires|Recommends):.*\b(speakersafetyd|speakerguardd)\b(?!-v2)')
        for name in requires:
            self.assertFalse(name.startswith(('kernel', 'uboot', 'm1n1')) or name == 'aura', name)
        self.assertNotIn('aurora-release', requires)
        self.assertNotIn('aurora-bless', requires)
        for name in ['asahi-platform-metapackage', 'asahi-platform-metapackage-core']:
            self.assertRegex(core, r'(?m)^Obsoletes: ' + name + r' < 1$')
        self.assertEqual((d / 'aurora-platform-core.conf').read_text().split(), ['aurora-platform-core'])
        self.assertIn('protected.d/aurora-platform-core.conf', text.split('%files core', 1)[1])
        self.assertRegex(text, r'(?m)^Requires: aurora-platform-core = %\{version\}-%\{release\}$')
    def test_speakerguardd_v2_is_the_only_speaker_stack(self):
        # Every install has aurora-audio: it brings v2 and the upgrade tool and
        # retires the Asahi stack on the upgrade. No recipe of it remains.
        spec = (ROOT / 'packages/speakerguardd-v2/speakerguardd-v2.spec').read_text()
        self.assertRegex(spec, r'(?m)^Release: 0\.(6[3-9]|[7-9][0-9])\.')
        self.assertIn('install -Dm644 packaging/session/parity.json', spec)
        # The speaker graph needs Aurora's PipeWire; Fedora's never provides it.
        self.assertRegex(spec, r'(?m)^Requires: pipewire-speaker-graph >= 2$')
        pw = (ROOT / 'packages/pipewire/pipewire.spec').read_text()
        libs = pw.split('%package libs', 1)[1].split('%description libs', 1)[0]
        self.assertRegex(libs, r'(?m)^Provides:\s+pipewire-speaker-graph = 2$')
        for n in ('1006', '1007', '1008', '1010'):
            self.assertRegex(pw, rf'(?m)^Patch{n}:')
        # No gate drop-in for daemons that no longer exist.
        self.assertNotIn('legacy-gate.conf %{buildroot}', spec)
        self.assertNotRegex(spec, r'(?m)^%\{_unitdir\}/(speakersafetyd|speakerguardd)\.service\.d')
        for name in ('speakersafetyd', 'speakersafetyd-aurora-profiles', 'speakerguardd'):
            self.assertFalse((ROOT / 'packages' / name).exists(), name)
        pins = json.loads((ROOT / 'sources.json').read_text())
        for name in ('speakersafetyd', 'speakerguardd'):
            self.assertNotIn(name, pins)
        audio = (ROOT / 'packages/aurora-audio/aurora-audio.spec').read_text()
        self.assertRegex(audio, r'(?m)^Requires: speakerguardd-v2 >= 1\.0\.0~alpha\.2-0\.63 aurora-speaker-upgrade$')
        for line in ('Obsoletes: speakersafetyd', 'Obsoletes: speakersafetyd-aurora-profiles',
                     'Obsoletes: speakerguardd < 0.2', 'Conflicts: speakersafetyd', 'Conflicts: speakerguardd < 0.2',
                     'Provides: asahi-audio = %{version}-%{release}', 'Obsoletes: asahi-audio < %{version}-%{release}',
                     'Conflicts: asahi-audio',
                     'Obsoletes: speakerguardd-v2 < 1.0.0~alpha.1-0.33', 'Conflicts: speakerguardd-v2 < 1.0.0~alpha.1-0.33'):
            self.assertRegex(audio, rf'(?m)^{re.escape(line)}$')
        self.assertNotRegex(audio, r'(?m)^(Requires|Recommends):.*\bspeakersafetyd\b')
        # The Asahi speaker graphs are not restored or installed for any Mac.
        self.assertNotIn('0001-restore-legacy-speaker-graphs.patch', audio)
        self.assertFalse((ROOT / 'packages/aurora-audio/0001-restore-legacy-speaker-graphs.patch').exists())
        self.assertRegex(audio, r'(?m)^Patch0: 0001-install-no-speaker-graphs\.patch$')
        patch = (ROOT / 'packages/aurora-audio/0001-install-no-speaker-graphs.patch').read_text()
        self.assertIn('-\tinstall -pm0644 conf/asahi-lock-volume.lua', patch)
        self.assertNotRegex(patch, r'(?m)^\+.*filter-path = .*/graph')
        # Kept: the period-interrupt rule and the dracut module.
        self.assertIn('99-aurora-speaker-irq.conf', audio)
        self.assertIn('90aurora-audio/module-setup.sh', audio)
        upgrade = (ROOT / 'packages/aurora-speaker-upgrade/aurora-speaker-upgrade.spec').read_text()
        self.assertRegex(upgrade, r'(?m)^Requires: speakerguardd-v2$')
        self.assertIn('%{_presetdir}/50-aurora-speaker-upgrade.preset', upgrade)
        preset = (ROOT / 'packages/aurora-speaker-upgrade/50-aurora-speaker-upgrade.preset').read_text()
        self.assertRegex(preset, r'(?m)^enable aurora-speaker-upgrade\.service$')
        self.assertNotIn('speakersafetyd', preset)
        # %systemd_post presets on the first install only: installs from before
        # the preset get it once, on the upgrade from an older build.
        post = upgrade.split('%triggerpostun -- aurora-speaker-upgrade < 0.1-0.27\n', 1)
        self.assertEqual(len(post), 2)
        self.assertTrue(post[1].startswith(
            'systemctl --no-reload --preset-mode=enable-only preset aurora-speaker-upgrade.service'))
        kernel = (ROOT / 'packages/kernel-aurora/kernel-aurora.spec').read_text()
        self.assertNotRegex(kernel, r'(?m)^(Requires|Recommends):.*\b(speakersafetyd|speakerguardd|speakerguardd-v2|aurora-speaker-upgrade)\b')
        self.assertIn('Requires: aurora-audio >= 4.1-12', kernel)
        self.assertIn('Requires: (aurora-platform-core >= 44-23 if aurora-platform-core)', kernel)
        images = (ROOT / 'images/configure.py').read_text()
        self.assertNotRegex(images, r'"(speakersafetyd[^"]*|speakerguardd)"')
        self.assertIn('"speakerguardd-v2"', images)

    def test_aurora_repos_owns_the_repository_key_and_vendor_policies(self):
        d = ROOT / 'packages' / 'aurora-repos'
        spec = (d / 'aurora-repos.spec').read_text()
        self.assertEqual((d / 'RPM-GPG-KEY-aurora').read_bytes(), (ROOT / 'keys' / 'RPM-GPG-KEY-aurora').read_bytes())
        repo = (d / 'aurora.repo').read_text()
        # The installed release picks its repository, and a release without
        # one stops a refresh or upgrade instead of dropping Aurora.
        self.assertIn('baseurl=https://aurorasilicon.org/fedora-aurora/$releasever/testing/aarch64\n', repo)
        for releasever in ('44', '45'):
            self.assertIn(f'baseurl=https://aurorasilicon.org/fedora-aurora/{releasever}/testing/aarch64\n',
                          repo.replace('$releasever', releasever))
        for line in ['gpgcheck=1', 'gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-aurora', 'skip_if_unavailable=False']:
            self.assertIn('\n' + line + '\n', repo)
        self.assertNotIn('repo_gpgcheck', repo)
        # The metadata signature is checked too. auto_import_local_keys
        # (libdnf5 >= 5.4.7) trusts the local key without a prompt, which an
        # unattended refresh could not answer. The override also covers a
        # locally changed aurora.repo.
        override = configparser.ConfigParser(interpolation=None)
        override.read_string((d / 'aurora-override.repo').read_text())
        self.assertEqual(override.sections(), ['aurora'])
        self.assertEqual(dict(override['aurora']), {'repo_gpgcheck': '1', 'auto_import_local_keys': '1'})
        self.assertRegex(spec, r'(?m)^Requires: libdnf5 >= 5\.4\.7$')
        self.assertIn('install -Dm644 %{SOURCE105} %{buildroot}/usr/share/dnf5/repos.override.d/50-aurora.repo', spec)
        files = spec.split('%files', 1)[1]
        self.assertIn('\n/usr/share/dnf5/repos.override.d/50-aurora.repo\n', files)
        self.assertIn('%config(noreplace) %{_sysconfdir}/yum.repos.d/aurora.repo', files)
        self.assertIn('/usr/share/dnf5/vendors.d/aurora*.conf', files)
        self.assertRegex(spec, r'(?m)^Conflicts: aurora-release < 44-8$')
        release = (ROOT / 'packages' / 'aurora-release' / 'aurora-release.spec').read_text()
        self.assertRegex(release, r'(?m)^Requires: aurora-repos$')
        self.assertNotIn('vendors.d', release)
        platform = (ROOT / 'packages' / 'aurora-platform' / 'aurora-platform.spec').read_text()
        core = platform.split('%package core', 1)[1].split('%description core', 1)[0]
        self.assertRegex(core, r'(?m)^Requires: aurora-repos$')
        build = (ROOT / 'scripts' / 'build-rpm').read_text()
        self.assertIn('[[ $package == aurora-release || $package == aurora-repos ]] && vendor=()', build)
    def test_splash_keeps_the_bootloader_logo_in_place(self):
        # aura draws its 128 or 256 px logo at ((w - size) / 2, (h - size) / 2) on
        # black; the splash draws the same images the same way, in device pixels.
        d = ROOT / 'packages' / 'plymouth-theme-aurora'
        for size in (128, 256):
            logo = (d / f'aurora-logo-{size}.png').read_bytes()
            self.assertEqual(logo[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II', logo[16:24]), (size, size))
        theme = dict(line.split('=', 1) for line in (d / 'aurora.plymouth').read_text().splitlines()
                     if '=' in line and not line.startswith('#'))
        self.assertEqual(theme['ModuleName'], 'script')
        # The distribution's spinner theme: its spinner, entry and watermark, which
        # initramfs generators copy as the theme's ImageDir.
        self.assertEqual(theme['ImageDir'], '/usr/share/plymouth/themes/spinner')
        self.assertEqual(theme['ScriptFile'], '/run/plymouth/aurora.script')
        script = (d / 'aurora.script').read_text()
        self.assertIn('logo_image[1] = Image("../aurora/aurora-logo-128.png");', script)
        self.assertIn('logo_image[2] = Image("../aurora/aurora-logo-256.png");', script)
        self.assertIn('return Math.Int((w - size) / 2);', script)
        self.assertIn('d.y + place_logo_y(d.w, d.h, logo.GetHeight()), 1);', script)
        self.assertIn('branding_source = Image("watermark.png");', script)
        spec = (d / 'plymouth-theme-aurora.spec').read_text()
        post = spec.split('%post', 1)[1].split('%postun', 1)[0]
        # Only a stock Fedora default gives way; an owner's other theme stays.
        self.assertIn("''|bgrt|spinner|charge)", post)
        # Plymouth's 2x scale would double the logo; the theme runs at scale 1.
        self.assertIn('DeviceScale=1', post)
        self.assertIn("! grep -qs '^[[:space:]]*DeviceScale[[:space:]]*=' $conf", post)
        self.assertIn('DeviceScale=1$/d}', spec.split('%postun', 1)[1])

    def run_theme_post(self, current, cmdline=None, entries=None, dracut_status=0):
        """Run the theme's %post and %posttrans against a fake Plymouth with CURRENT set."""
        spec = (ROOT / 'packages' / 'plymouth-theme-aurora' / 'plymouth-theme-aurora.spec').read_text()
        post = spec.split('\n%post\n', 1)[1].split('\n%posttrans\n', 1)[0]
        posttrans = spec.split('\n%posttrans\n', 1)[1].split('\n%postun\n', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'bin').mkdir()
            (tmp / 'etc/plymouth').mkdir(parents=True)
            (tmp / 'etc/plymouth/plymouthd.conf').write_text('[Daemon]\n' + (f'Theme={current}\n' if current else ''))
            state = tmp / 'theme'
            state.write_text(current or 'bgrt')
            log = tmp / 'dracut.log'
            fake = tmp / 'bin/plymouth-set-default-theme'
            fake.write_text(f'#!/bin/bash\n[[ $# -eq 0 ]] && exec cat {state}\nprintf %s "$1" > {state}\n')
            fake.chmod(0o755)
            dracut = tmp / 'bin/dracut'
            dracut.write_text(f'#!/bin/bash\necho "$@" >> {log}\nexit {dracut_status}\n')
            dracut.chmod(0o755)
            grubby = tmp / 'bin/grubby'
            grubby.write_text(f'#!/bin/bash\nif [[ $1 == --info=ALL ]]; then cat {tmp / "entries"} 2>/dev/null; exit 0; fi\n'
                              f'echo "$@" >> {tmp / "grubby.log"}\n')
            if entries is not None:
                (tmp / 'entries').write_text(entries)
            grubby.chmod(0o755)
            if cmdline is not None:
                (tmp / 'etc/kernel').mkdir()
                (tmp / 'etc/kernel/cmdline').write_text(cmdline + '\n')
            def render(script):
                return (script.replace('%{_bindir}', str(tmp / 'bin')).replace('%{_sbindir}', str(tmp / 'bin'))
                        .replace('%{_sysconfdir}', str(tmp / 'etc'))
                        .replace('%{_localstatedir}', str(tmp / 'var')).replace('/run/systemd/system', str(tmp)))
            env = dict(os.environ, PATH=f"{tmp / 'bin'}:{os.environ['PATH']}")
            subprocess.run(['bash', '-euc', render(post)], check=True, env=env)
            self.posttrans = subprocess.run(['bash', '-euc', render(posttrans)], env=env,
                                            capture_output=True, text=True)
            if not dracut_status:
                self.assertEqual(self.posttrans.returncode, 0, self.posttrans.stderr)
            self.grubby = (tmp / 'grubby.log').read_text() if (tmp / 'grubby.log').exists() else ''
            return state.read_text(), log.read_text() if log.exists() else ''

    def test_theme_keeps_a_serial_console_from_forcing_the_text_view(self):
        # The Neo's device tree names its DockChannel UART as stdout-path; with it as a
        # console Plymouth shows only its details view, passphrase prompt included.
        for cmdline, expected in (
                ('root=UUID=x ro rhgb quiet user4k=on', '--update-kernel=ALL --args=plymouth.ignore-serial-consoles'),
                ('root=UUID=x ro rhgb quiet plymouth.ignore-serial-consoles', ''),
                ('root=UUID=x ro quiet', ''),
                (None, '')):
            with self.subTest(cmdline=cmdline):
                self.run_theme_post('aurora', cmdline)
                self.assertEqual(self.grubby.strip(), expected)
        # Entries made before the argument reached /etc/kernel/cmdline still get it.
        fix = '--update-kernel=ALL --args=plymouth.ignore-serial-consoles'
        for entries, expected in (
                ('kernel="/boot/vmlinuz-a"\nargs="ro rhgb quiet"\n', fix),
                ('args="ro rhgb quiet plymouth.ignore-serial-consoles"\n', ''),
                ('args="ro quiet"\n', '')):
            with self.subTest(entries=entries):
                self.run_theme_post('aurora', 'root=UUID=x ro rhgb quiet plymouth.ignore-serial-consoles', entries)
                self.assertEqual(self.grubby.strip(), expected)

    def test_theme_replaces_only_a_stock_default_and_rebuilds_the_initramfs(self):
        for stock in ('', 'bgrt', 'spinner', 'charge'):
            theme, dracut = self.run_theme_post(stock)
            self.assertEqual(theme, 'aurora', stock)
            self.assertEqual(dracut.strip(), '-f --regenerate-all', stock)

    def test_theme_reports_a_failed_initramfs_rebuild(self):
        theme, dracut = self.run_theme_post('aurora', dracut_status=1)
        self.assertEqual(dracut.strip(), '-f --regenerate-all')
        self.assertNotEqual(self.posttrans.returncode, 0)
        self.assertIn('rebuilding the initramfs failed', self.posttrans.stderr)

    def test_theme_keeps_the_owners_choice(self):
        for chosen in ('solar', 'details'):
            theme, dracut = self.run_theme_post(chosen)
            self.assertEqual(theme, chosen)
            self.assertEqual(dracut, '')

    def test_theme_update_rebuilds_the_initramfs(self):
        # The initramfs carries its own copy of the theme and plymouthd.conf, so an
        # update of the selected theme must reach it, not only a switch to it.
        theme, dracut = self.run_theme_post('aurora')
        self.assertEqual(theme, 'aurora')
        self.assertEqual(dracut.strip(), '-f --regenerate-all')

    def test_kernel_ships_the_page_size_launcher_from_its_own_source(self):
        spec = (ROOT / 'packages' / 'kernel-aurora' / 'kernel-aurora.spec').read_text()
        main = spec.split('%package core', 1)[0]
        # Unversioned, so an older installed kernel never holds back the launcher.
        self.assertRegex(main, r'(?m)^Requires: aurora-userpages$')
        package = spec.split('%package -n aurora-userpages', 1)[1].split('%description -n aurora-userpages', 1)[0]
        self.assertNotIn('installonlypkg', package)
        self.assertIn('\nmake -C tools/aurora-userpages\n', spec.split('%build', 1)[1].split('%install', 1)[0])
        self.assertIn('install -Dm755 tools/aurora-userpages/userpages %{buildroot}%{_bindir}/userpages', spec)
        files = spec.split('%files -n aurora-userpages', 1)[1].split('%changelog', 1)[0]
        self.assertIn('%{_bindir}/userpages\n', files)
        self.assertIn('%{_docdir}/aurora-userpages/\n', files)

    def test_page_size_launcher_turns_user4k_on_and_keeps_an_owner_choice(self):
        spec = (ROOT / 'packages' / 'kernel-aurora' / 'kernel-aurora.spec').read_text()
        scriptlet = spec.split('%posttrans -n aurora-userpages\n', 1)[1].split('\n%', 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bindir = root / 'bin'
            bindir.mkdir()
            (bindir / 'grubby').write_text('#!/bin/sh\necho "$*" >> "$GRUBBY_LOG"\n')
            (bindir / 'grubby').chmod(0o755)
            cmdline, log = root / 'cmdline', root / 'grubby.log'
            script = scriptlet.replace('/etc/kernel/cmdline', str(cmdline))
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", GRUBBY_LOG=str(log))
            for content, called in ((None, False), ('root=UUID=r ro quiet\n', True),
                                    ('root=UUID=r ro user4k=off quiet\n', False),
                                    ('root=UUID=r ro quiet user4k=on\n', False)):
                with self.subTest(cmdline=content):
                    log.write_text('')
                    if content is None:
                        cmdline.unlink(missing_ok=True)
                    else:
                        cmdline.write_text(content)
                    subprocess.run(['sh', '-ec', script], env=env, check=True)
                    self.assertEqual(log.read_text(), '--update-kernel=ALL --args=user4k=on\n' if called else '')
    def test_fex_replaces_fedoras_under_its_names(self):
        # dnf resolves `fex-emu` by name; the Aurora repository's priority then
        # picks these over Fedora's. `fex` stays Fedora's unrelated tool.
        spec = (ROOT / 'packages' / 'fex-emu' / 'fex-emu.spec').read_text()
        self.assertRegex(spec, r'(?m)^Name:\s+fex-emu$')
        self.assertRegex(spec, r'(?m)^Release:\s+\d+%\{\?dist\}\.aurora$')
        self.assertGreaterEqual(int(re.search(r'(?m)^Version:\s+(\d+)$', spec).group(1)), 2604)
        self.assertNotRegex(spec, r'(?m)^%package\s+-n fex$')
        self.assertNotRegex(spec, r'(?m)^Provides:\s+fex(\s|$)')
        for name in ('filesystem', 'devel', 'utils', 'thunks'):
            self.assertRegex(spec, rf'(?m)^%package\s+{re.escape(name)}$')
        self.assertRegex(spec, r'(?m)^Requires:\s+%\{name\}%\{\?_isa\} = %\{version\}-%\{release\}$')
        repo = (ROOT / 'packages' / 'aurora-repos' / 'aurora.repo').read_text()
        self.assertIn('\npriority=1\n', repo)

    def test_binfmt_dispatcher_runs_fex_in_a_4k_tree(self):
        d = ROOT / 'packages' / 'fex-emu'
        conf = (d / '50-aurora-fex.toml').read_text()
        self.assertIn('path = "/usr/libexec/fex-emu/fex-userpages"', conf)
        self.assertIn('use_muvm = false', conf)
        self.assertNotIn('FEXInterpreter"', conf)
        wrapper = (d / 'fex-userpages').read_text()
        self.assertIn('exec /usr/bin/userpages 4k /usr/bin/FEX "$@"', wrapper)
        subprocess.run(['sh', '-n', str(d / 'fex-userpages')], check=True)
        spec = (d / 'fex-emu.spec').read_text()
        self.assertIn('%{_prefix}/lib/binfmt-dispatcher.d/50-aurora-fex.toml\n', spec.split('%files\n', 1)[1])
        self.assertRegex(spec, r'(?m)^Requires:\s+aurora-userpages$')

    def test_fex_is_the_only_x86_binfmt_handler(self):
        # Fixtures: FEX's handlers from the fork's Data/binfmts at the pinned
        # commit (prefix /usr), and binfmt-dispatcher's from Fedora 44's and
        # 45's aarch64 binfmt-dispatcher 0.1.2, which Fedora Asahi Remix
        # installs. Both match the same programs; binfmt-dispatcher's file
        # names sort after FEX's.
        d = ROOT / 'packages' / 'fex-emu'
        fixtures = ROOT / 'tests' / 'fixtures' / 'binfmt'
        spec = (d / 'fex-emu.spec').read_text()
        fex = {f'FEX-{arch}.conf': (fixtures / f'FEX-{arch}.conf').read_text() for arch in ('x86', 'x86_64')}
        dispatcher = {f.name: f.read_text() for f in fixtures.glob('zz-binfmt-dispatcher-*.conf')}
        self.assertEqual(sorted(dispatcher), ['zz-binfmt-dispatcher-x86.conf', 'zz-binfmt-dispatcher-x86_64.conf'])
        for arch in ('x86', 'x86_64'):
            ours = binfmt_registrations({'/usr/lib/binfmt.d': {'a.conf': fex[f'FEX-{arch}.conf']}})[0]
            theirs = binfmt_registrations({'/usr/lib/binfmt.d': {'a.conf': dispatcher[f'zz-binfmt-dispatcher-{arch}.conf']}})[0]
            self.assertEqual((ours['magic'], ours['mask']), (theirs['magic'], theirs['mask']))
        # fex-emu installs one file under each of binfmt-dispatcher's names in
        # /etc/binfmt.d, which systemd-binfmt reads instead of /usr/lib's.
        source = re.search(r'(?m)^Source(\d+):\s+binfmt-dispatcher-x86-off\.conf$', spec).group(1)
        names = re.search(r'(?m)^for f in (.+); do\n  install -Dm644 %\{SOURCE' + source +
                          r'\} %\{buildroot\}%\{_sysconfdir\}/binfmt\.d/\$f\ndone$', spec).group(1).split()
        self.assertEqual(sorted(names), sorted(dispatcher))
        files = spec.split('%files\n', 1)[1].split('%files', 1)[0]
        for name in names:
            self.assertIn(f'%config(noreplace) %{{_sysconfdir}}/binfmt.d/{name}\n', files)
        mask = (d / 'binfmt-dispatcher-x86-off.conf').read_text()
        for line in mask.splitlines():
            self.assertTrue(line == '' or line.startswith('#'), line)
        self.assertIn('sudo cp /usr/lib/binfmt.d/zz-binfmt-dispatcher-x86*.conf /etc/binfmt.d/', mask)
        masks = dict.fromkeys(names, mask)
        programs = {'FEX-x86_64': [x86_elf_header(64, t) for t in (2, 3)],
                    'FEX-x86': [x86_elf_header(32, t) for t in (2, 3)]}
        # A fresh install, and an Asahi upgrade (or binfmt-dispatcher installed
        # later: rpm's binfmt.d trigger reruns all of systemd-binfmt).
        for case, tree in (('fresh install', {'/usr/lib/binfmt.d': fex}),
                           ('beside binfmt-dispatcher', {'/usr/lib/binfmt.d': {**fex, **dispatcher}, '/etc/binfmt.d': masks})):
            with self.subTest(case=case):
                handlers = binfmt_registrations(tree)
                self.assertEqual(sorted(h['name'] for h in handlers), ['FEX-x86', 'FEX-x86_64'])
                for name, headers in programs.items():
                    for header in headers:
                        h = binfmt_handler(handlers, header)
                        self.assertEqual((h['name'], h['interpreter'], h['flags']), (name, '/usr/bin/FEX', 'POCF'))
                aarch64 = b'\x7fELF\x02\x01\x01' + bytes(9) + struct.pack('<HH', 2, 183)
                self.assertIsNone(binfmt_handler(handlers, aarch64))
        # Without the masks (fex-emu 2610-6), binfmt-dispatcher's handlers won.
        handlers = binfmt_registrations({'/usr/lib/binfmt.d': {**fex, **dispatcher}})
        self.assertEqual(binfmt_handler(handlers, x86_elf_header(64))['name'], 'binfmt-dispatcher-x86_64')
        # An owner's copy of binfmt-dispatcher's files turns them back on.
        handlers = binfmt_registrations({'/usr/lib/binfmt.d': {**fex, **dispatcher}, '/etc/binfmt.d': dict(dispatcher)})
        self.assertEqual(binfmt_handler(handlers, x86_elf_header(32))['name'], 'binfmt-dispatcher-x86')
        # The build checks its own handlers against the same fields.
        self.assertIn('grep -Eqx ":FEX-$arch:M:0:[^:]+:[^:]+:%{_bindir}/FEX:POCF" %{buildroot}%{_binfmtdir}/FEX-$arch.conf\n', spec)
        for text in fex.values():
            self.assertRegex(text, r'\A:FEX-x86(_64)?:M:0:[^:]+:[^:]+:/usr/bin/FEX:POCF\n\Z')
        self.assertIn('/etc/binfmt.d', (d / 'README.aurora').read_text())

    def test_fex_userpages_passes_the_programs_own_arguments(self):
        d = ROOT / 'packages' / 'fex-emu'
        script = (d / 'fex-userpages').read_text()
        subprocess.run(['sh', '-n', str(d / 'fex-userpages')], check=True)
        # fex-emu 2610-6's fex-userpages.
        old = ('#!/bin/sh\n[ "$(getconf PAGE_SIZE)" = 4096 ] && exec /usr/bin/FEX "$@"\n'
               'exec /usr/bin/userpages 4k /usr/bin/FEX "$@"\n')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            log, bindir = root / 'fex.log', root / 'bin'
            fex, userpages, getconf = root / 'FEX', root / 'userpages', bindir / 'getconf'
            bindir.mkdir()
            # FEX's stand-in: its arguments, FEX_EXECVEFD(_PATH) and the file on that fd.
            fex.write_text('#!/bin/sh\n'
                           '{ for a in "$@"; do printf "arg %s\\n" "$a"; done\n'
                           '  printf "fd %s\\npath %s\\n" "${FEX_EXECVEFD-}" "${FEX_EXECVEFD_PATH-}"\n'
                           '  [ -z "${FEX_EXECVEFD-}" ] || printf "target %s\\n" "$(readlink "/proc/$$/fd/$FEX_EXECVEFD")"\n'
                           '} > "$FEX_LOG"\n')
            userpages.write_text('#!/bin/sh\necho "$1" > "$FEX_LOG.userpages"\nshift\nexec "$@"\n')
            getconf.write_text('#!/bin/sh\n[ "$1" = PAGE_SIZE ] && echo "$TEST_PAGE_SIZE"\n')
            program = root / 'x86 programs' / 'prog'
            program.parent.mkdir()
            program.write_bytes(x86_elf_header(64))
            for f in (fex, userpages, getconf, program):
                f.chmod(0o755)

            def run(text, args, page, fd3=None):
                for path in ('/usr/bin/userpages', '/usr/bin/FEX'):
                    self.assertIn(path, text)
                wrapper = root / 'fex-userpages'
                wrapper.write_text(text.replace('/usr/bin/userpages', str(userpages)).replace('/usr/bin/FEX', str(fex)))
                for f in (log, root / 'fex.log.userpages'):
                    f.unlink(missing_ok=True)
                env = {k: v for k, v in os.environ.items() if not k.startswith('FEX_')}
                env.update(PATH=f'{bindir}:{os.environ["PATH"]}', FEX_LOG=str(log), TEST_PAGE_SIZE=str(page))
                cmd = ['sh', str(wrapper), *args]
                if fd3 is not None:
                    # As binfmt_misc leaves it for binfmt-dispatcher: the program on fd 3.
                    cmd = ['sh', '-c', 'exec 3<"$1"; shift; exec "$@"', 'sh', str(fd3), *cmd]
                subprocess.run(cmd, env=env, check=True, cwd=root, stdin=subprocess.DEVNULL)
                record = {'args': []}
                for line in log.read_text().splitlines():
                    key, _, value = line.partition(' ')
                    if key == 'arg':
                        record['args'].append(value)
                    else:
                        record[key] = value
                up = root / 'fex.log.userpages'
                record['userpages'] = up.read_text().strip() if up.exists() else None
                return record

            # binfmt-dispatcher runs its interpreter as INTERPRETER PROGRAM PATH
            # ARGV0 [ARG...]: PROGRAM is the file on fd 3, and PATH and ARGV0
            # what execve was given (its handlers' P flag).
            path, argv0, args = './x86 programs/prog', 'custom-argv0', ['one', 'two words', '']
            dispatched = [str(program), path, argv0, *args]
            for page, launcher in ((16384, '4k'), (4096, None)):
                with self.subTest(page=page, via='binfmt-dispatcher'):
                    r = run(script, dispatched, page, fd3=program)
                    self.assertEqual(r['args'], [path, argv0, *args])
                    self.assertEqual((r['fd'], r['path'], r.get('target')), ('3', '1', str(program)))
                    self.assertEqual(fex_guest_argv(r['args'], int(r['fd'])), [argv0, *args])
                    self.assertEqual(r['userpages'], launcher)
                with self.subTest(page=page, via='fex-userpages PROGRAM [ARG...]'):
                    r = run(script, [path, *args], page)
                    self.assertEqual((r['args'], r['fd']), ([path, *args], ''))
                    self.assertEqual(fex_guest_argv(r['args'], 0), [path, *args])
                    self.assertEqual(r['userpages'], launcher)
            with self.subTest(case='fd 3 open on another file'):
                r = run(script, dispatched, 4096, fd3='/dev/null')
                self.assertEqual((r['args'], r['fd']), (dispatched, ''))
            with self.subTest(case='fex-emu 2610-6'):
                # The program got its own path as argv[1], and ARGV0 as argv[2].
                r = run(old, dispatched, 4096, fd3=program)
                self.assertEqual(fex_guest_argv(r['args'], int(r['fd'] or 0)), [str(program), path, argv0, *args])

    def test_fex_mounts_the_stock_guest_rootfs_below_the_aurora_mesa_layer(self):
        d = ROOT / 'packages' / 'fex-emu'
        unit = configparser.ConfigParser(strict=False)
        unit.optionxform = str
        unit.read_string((d / 'usr-share-guestos-fex\\x2dmesa.mount').read_text())
        self.assertEqual(dict(unit['Mount']), {'What': '/usr/share/fex-emu/RootFS/default.erofs',
                                               'Where': '/usr/share/guestos/fex-mesa', 'Type': 'erofs',
                                               'Options': 'ro,loop,nodev,nosuid'})
        self.assertEqual(unit['Unit']['ConditionDirectoryNotEmpty'], '!/usr/share/guestos/fex-mesa')
        # The provider service (mesa-aurora-fex-guest) lays its layer over this mount point.
        service = (ROOT / 'packages/mesa-aurora-fex-guest/aurora-fex-mesa.service').read_text()
        self.assertIn('lowerdir=/usr/share/guestos/aurora-fex-mesa-layer:/usr/share/guestos/fex-mesa ', service)
        dropin = (d / '50-aurora-fex-rootfs.conf').read_text()
        self.assertIn('Wants=usr-share-guestos-fex\\x2dmesa.mount\n', dropin)
        self.assertIn('After=usr-share-guestos-fex\\x2dmesa.mount\n', dropin)
        spec = (d / 'fex-emu.spec').read_text()
        files = spec.split('%files\n', 1)[1].split('%files', 1)[0]
        for path in ('%{_unitdir}/usr-share-guestos-fex*.mount', '%{_unitdir}/aurora-fex-mesa.service.d/50-aurora-fex-rootfs.conf'):
            self.assertIn(path + '\n', files)
        self.assertIn('%triggerin -- fex-emu-rootfs-fedora\n%{_libexecdir}/fex-emu/aurora-fex-provider-up\n', spec)
        subprocess.run(['sh', '-n', str(d / 'aurora-fex-provider-up')], check=True)

    def test_fex_defaults_to_the_fedora_rootfs_image(self):
        d = ROOT / 'packages' / 'fex-emu'
        spec = (d / 'fex-emu.spec').read_text()
        # FEX reads its global config from DATA_DIRECTORY, by default
        # ${CMAKE_INSTALL_PREFIX}/share/fex-emu; a user's Config.json overrides it.
        self.assertNotIn('-DDATA_DIRECTORY', spec)
        self.assertIn('%cmake -G Ninja', spec)
        config = json.loads((d / 'Config.json').read_text())
        image = '/usr/share/fex-emu/RootFS/default.erofs'
        self.assertEqual(config, {'Config': {'RootFS': image}})
        unit = configparser.ConfigParser(strict=False)
        unit.optionxform = str
        unit.read_string((d / 'usr-share-guestos-fex\\x2dmesa.mount').read_text())
        self.assertEqual(unit['Mount']['What'], image)
        source = re.search(r'(?m)^Source(\d+):\s+Config\.json$', spec).group(1)
        self.assertIn(f'install -Dm644 %{{SOURCE{source}}} %{{buildroot}}%{{_datadir}}/fex-emu/Config.json\n', spec)
        files = spec.split('%files\n', 1)[1].split('%files', 1)[0]
        self.assertIn('%config(noreplace) %{_datadir}/fex-emu/Config.json\n', files)

    def test_fex_requires_what_mounts_its_rootfs_and_names_the_image_package(self):
        d = ROOT / 'packages' / 'fex-emu'
        spec = (d / 'fex-emu.spec').read_text()
        main = spec.split('%package', 1)[0]
        # FEXServer runs erofsfuse on the .erofs image; fusermount3 mounts it for a user.
        for name in ('erofs-fuse', 'fuse3'):
            self.assertRegex(main, rf'(?m)^Requires:\s+{name}$')
            self.assertNotRegex(main, rf'(?m)^Recommends:\s+{name}$')
        # The 1.9 GB image stays a weak dependency, which dnf installs by default.
        self.assertRegex(main, r'(?m)^Recommends:\s+fex-emu-rootfs-fedora$')
        patch = re.search(r'(?m)^Patch0:\s+(\S+)$', spec).group(1)
        text = (d / patch).read_text()
        self.assertIn('add_compile_definitions(ROOTFS_PACKAGE="${ROOTFS_PACKAGE}")', text)
        self.assertIn('Install the {} package for the default RootFS', text)
        # A 4K page process can't read /dev/fuse on Aurora kernels: FEXServer
        # runs erofsfuse with native pages.
        native = (d / re.search(r'(?m)^Patch1:\s+(\S+)$', spec).group(1)).read_text()
        self.assertIn('+++ b/Source/Tools/FEXServer/SquashFS.cpp', native)
        for line in ('+    prctl(PR_AURORA_SET_DEFAULT_PAGE_SIZE, 0UL, 0UL, 0UL, 0UL);',
                     '+    prctl(PR_AURORA_SET_EXEC_PAGE_SIZE, 0UL, 0UL, 0UL, 0UL);'):
            self.assertIn(line, native)
        prep = spec.split('%prep\n', 1)[1].split('%build\n', 1)[0]
        self.assertIn('\n%autopatch -p1\n', prep)
        self.assertIn('    -DROOTFS_PACKAGE=fex-emu-rootfs-fedora \\\n', spec.split('%cmake -G Ninja', 1)[1])

    def test_fex_uses_the_aurora_mesa_provider_while_it_is_mounted(self):
        d = ROOT / 'packages' / 'fex-emu'
        spec = (d / 'fex-emu.spec').read_text()
        main = spec.split('%package', 1)[0]
        # Pulled in where Aurora's host Mesa is (the guest requires its exact
        # build); rich, so Fedora's own Mesa pulls nothing and dnf5's weak
        # dependency autodetection never excludes it.
        self.assertRegex(main, r'(?m)^Recommends:\s+\(mesa-aurora-fex-guest if mesa-aurora-dri-drivers\)$')
        self.assertNotRegex(main, r'(?m)^Requires:.*mesa-aurora-fex-guest')
        guest = (ROOT / 'packages/mesa-aurora-fex-guest/mesa-aurora-fex-guest.spec').read_text()
        self.assertRegex(guest, r'(?m)^Requires: mesa-dri-drivers = %\{version\}-%\{release\}$')
        host = (ROOT / 'packages/mesa-aurora/mesa-aurora.spec').read_text()
        self.assertRegex(host, r'(?m)^%package -n mesa-aurora-dri-drivers$')
        self.assertRegex(main, r'(?m)^Requires:\s+util-linux-core$')
        # FEX reads the runtime config over the global one, in the global layer only.
        patch = (d / re.search(r'(?m)^Patch2:\s+(\S+)$', spec).group(1)).read_text()
        self.assertIn('+++ b/Source/Common/Config.cpp', patch)
        self.assertIn('+  if (GetLayerType() == FEXCore::Config::LayerType::LAYER_GLOBAL_MAIN) {', patch)
        self.assertIn('+    const fextl::string RuntimeConfig {"/run/fex-emu/Config.json"};', patch)
        self.assertIn('grep -qaF /run/fex-emu/Config.json %{buildroot}%{_bindir}/FEX\n', spec)
        # The provider's service drives the selection.
        source = re.search(r'(?m)^Source(\d+):\s+aurora-fex-rootfs$', spec).group(1)
        self.assertIn(f'install -Dm755 %{{SOURCE{source}}} %{{buildroot}}%{{_libexecdir}}/fex-emu/aurora-fex-rootfs\n', spec)
        unit = configparser.ConfigParser(strict=False)
        unit.optionxform = str
        unit.read_string((d / '50-aurora-fex-rootfs.conf').read_text())
        for key in ('ExecStartPost', 'ExecStopPost'):
            self.assertEqual(unit['Service'][key], '-/usr/libexec/fex-emu/aurora-fex-rootfs')
        self.assertEqual(unit['Unit']['Before'], 'systemd-user-sessions.service')
        script = (d / 'aurora-fex-rootfs').read_text()
        for line in ('provider=/usr/share/guestos/aurora-fex-mesa\n', 'rootfs=$dir/rootfs\n',
                     'config=$dir/Config.json\n'):
            self.assertIn(line, script)
        subprocess.run(['sh', '-n', str(d / 'aurora-fex-rootfs')], check=True)
        self.assertIn('/usr/libexec/fex-emu/aurora-fex-rootfs || :\n', (d / 'aurora-fex-provider-up').read_text())
        self.assertIn('%triggerpostun -- mesa-aurora-fex-guest\n'
                      '[ $2 -gt 0 ] || %{_libexecdir}/fex-emu/aurora-fex-rootfs || :\n', spec)
        # The installed global config still names the stock image.
        self.assertEqual(json.loads((d / 'Config.json').read_text()),
                         {'Config': {'RootFS': '/usr/share/fex-emu/RootFS/default.erofs'}})

    def test_fex_submodules_are_pinned_with_the_fork(self):
        spec = (ROOT / 'packages' / 'fex-emu' / 'fex-emu.spec').read_text()
        pin = json.loads((ROOT / 'sources.json').read_text())['fex-emu']
        self.assertEqual(pin['repository'], 'https://github.com/aurora-silicon/fex')
        self.assertRegex(spec, rf'(?m)^%global commit {pin["commit"]}$')
        self.assertIn(f'%autosetup -N -n {pin["archive_root"].replace(pin["commit"], "%{commit}")}', spec)
        bundled = {name: record for name, record in pin['extra_sources'].items() if name != 'fex-sysroot'}
        declared = re.findall(r'(?m)^Source1\d\d:\s+(\S+)$', spec)
        self.assertEqual(sorted(declared), sorted(f'{name}-{record["commit"]}.tar.gz' for name, record in bundled.items()))
        unpacked = re.findall(r'(?m)^unpack %\{SOURCE(1\d\d)\} \S+$', spec)
        self.assertEqual(len(unpacked), len(declared))
        sysroot = pin['extra_sources']['fex-sysroot']
        version = re.search(r'(?m)^%global sysroot_version (\S+)$', spec).group(1)
        self.assertEqual(sysroot['archive_file'], f'fex-sysroot-{version}.tar.gz')

    def test_steam_is_the_native_arm64_launcher(self):
        d = ROOT / 'packages' / 'aurora-steam-native'
        spec = (d / 'aurora-steam-native.spec').read_text()
        self.assertRegex(spec, r'(?m)^%package -n steam$')
        files = spec.split('%files -n steam', 1)[1].split('%changelog', 1)[0]
        self.assertIn('%{_bindir}/steam\n', files)
        # libibus and lsof come from the host (aurora-silicon/aurora-steam-native#13).
        for requirement in ('aurora-userpages', 'fex-emu', 'gtk2', 'ibus-libs', 'lsof'):
            self.assertRegex(spec, rf'(?m)^Requires: {requirement}$')
        # Fedora installs the launcher on PATH, not where the upstream default looks.
        self.assertIn("s,@USERPAGES@,%{_bindir}/userpages,", spec)
        wrapper = (d / 'steam').read_text()
        self.assertIn('userpages=${AURORA_USERPAGES_LAUNCHER:-@USERPAGES@}\nexport AURORA_USERPAGES_LAUNCHER=$userpages\n', wrapper)
        self.assertIn('"$userpages" 4k true', wrapper)
        self.assertIn('exec "$lib/bin/steam-native4k" "$@"', wrapper)
        subprocess.run(['bash', '-n', str(d / 'steam')], check=True)
        # Games run under GameMode; desktops get it on upgrade too.
        steam = spec.split('%package -n steam', 1)[1].split('%description', 1)[0]
        self.assertRegex(steam, r'(?m)^Recommends: aurora-gamemode$')
        platform = (ROOT / 'packages/aurora-platform/aurora-platform.spec').read_text().split('%package core', 1)[0]
        self.assertRegex(platform, r'(?m)^Recommends: \(aurora-gamemode if \(plasma-workspace or gnome-shell\)\)$')
        self.assertIn('AURORA_STEAM_GAMEMODE', wrapper)

    def test_steam_wrapper_installs_once_then_starts_the_client(self):
        d = ROOT / 'packages' / 'aurora-steam-native'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lib, home = root / 'lib', root / 'home'
            (lib / 'bin').mkdir(parents=True)
            home.mkdir()
            log = root / 'log'
            (lib / 'install-steam-arm64.py').write_text(
                'import os, pathlib, sys\n'
                'home = pathlib.Path(os.environ["HOME"])\n'
                'client = home / "client/steamrtarm64"; client.mkdir(parents=True)\n'
                '(client / "steam").write_text(""); (client / "steam").chmod(0o755)\n'
                '(home / ".steam").mkdir(); (home / ".steam/root").symlink_to(home / "client")\n'
                f'open({str(log)!r}, "a").write("install " + " ".join(sys.argv[1:]) + "\\n")\n')
            (lib / 'bin/steam-native4k').write_text(f'#!/bin/sh\necho "start $AURORA_USERPAGES_LAUNCHER $*" >> {log}\n')
            (lib / 'bin/steam-native4k').chmod(0o755)
            userpages = root / 'userpages'
            userpages.write_text('#!/bin/sh\n[ "$1" = 4k ] && [ -z "$NO_USER4K" ]\n')
            userpages.chmod(0o755)
            wrapper = root / 'steam'
            wrapper.write_text((d / 'steam').read_text().replace('@LIBDIR@', str(lib)).replace('@USERPAGES@', str(userpages))
                               .replace('@USER4K_HINT@', 'user4k=on hint'))
            wrapper.chmod(0o755)
            env = {'HOME': str(home), 'PATH': os.environ['PATH'], 'USER': 'test'}
            for _ in range(2):
                subprocess.run([str(wrapper), '-silent'], env=env, check=True, capture_output=True)
            lines = log.read_text().splitlines()
            self.assertEqual(lines[0], f'install --prefix {home}/.local/state/aurora-steam-native/prefix')
            self.assertEqual(lines[1:], [f'start {userpages} -silent'] * 2)
            result = subprocess.run([str(wrapper)], env={**env, 'NO_USER4K': '1'}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('user4k=on', result.stderr)

    def test_steam_registers_each_game_process_with_gamemode(self):
        # The watcher follows the client's logs/gameprocess_log.txt through
        # inotify, registers every tracked PID and sleeps in between.
        def watchers(root):
            found = []
            for proc in Path('/proc').iterdir():
                try:
                    argv = (proc / 'cmdline').read_bytes().split(b'\0')
                except OSError:
                    continue
                if argv[0] == b'aurora-steam-gamemode' and str(root).encode() in b' '.join(argv):
                    found.append(proc)
            return found

        def wait(condition):
            deadline = time.monotonic() + 10
            while not condition():
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.05)

        def switches(proc):
            status = (proc / 'status').read_text()
            return int(re.search(r'(?m)^voluntary_ctxt_switches:\s+(\d+)$', status)[1])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lib, home, stubs, client = root / 'lib', root / 'home', root / 'stubs', root / 'client'
            for path in (lib / 'bin', client / 'steamrtarm64', client / 'logs', stubs, home / '.steam'):
                path.mkdir(parents=True)
            (home / '.steam/root').symlink_to(client)
            gamelog, log = client / 'logs/gameprocess_log.txt', root / 'busctl.log'
            gamelog.write_text('[2026-11-17 19:14:50] AppID 9 adding PID 999 as a tracked process\n')
            log.write_text('')
            bash = shutil.which('bash')

            def script(path, body):
                path.write_text(f'#!{bash}\n' + body)
                path.chmod(0o755)
            script(client / 'steamrtarm64/steam', '')
            script(lib / 'bin/steam-native4k', 'exec sleep 60\n')
            script(root / 'userpages', '')
            script(stubs / 'busctl', f'echo "busctl $*" >> {log}\n'
                   'case "$*" in *ListActivatableNames*) echo \'as 2 "org.freedesktop.DBus" "com.feralinteractive.GameMode"\';; esac\n')
            wrapper = root / 'steam'
            wrapper.write_text((ROOT / 'packages' / 'aurora-steam-native' / 'steam').read_text().replace('@LIBDIR@', str(lib))
                               .replace('@USERPAGES@', str(root / 'userpages')).replace('@USER4K_HINT@', 'hint'))
            wrapper.chmod(0o755)
            env = {'HOME': str(home), 'PATH': f'{stubs}:{os.environ["PATH"]}', 'USER': 'test'}

            def registered():
                return [line.split()[-1] for line in log.read_text().splitlines() if 'RegisterGameByPID ii' in line]

            steam = subprocess.Popen([bash, str(wrapper)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                wait(lambda: len(watchers(client)) == 1)
                watcher = watchers(client)[0]
                wait(lambda: (watcher / 'stat').read_text().rsplit(')', 1)[1].split()[0] == 'S')
                with gamelog.open('a') as f:
                    f.write('[2026-11-20 10:00:00] AppID 383870 adding PID 4242 as a tracked process "x"\n'
                            '[2026-11-20 10:00:00] AppID 383870 adding PID 4243 as a')
                wait(lambda: registered() == ['4242'])
                with gamelog.open('a') as f:
                    f.write(' tracked process\n')
                wait(lambda: registered() == ['4242', '4243'])
                # Idle: blocked in select(), no wake-ups at all.
                time.sleep(0.5)
                before = switches(watcher)
                time.sleep(2)
                self.assertEqual(switches(watcher), before)
                # Steam rotates the log and starts a new one.
                gamelog.rename(gamelog.with_name('gameprocess_log.previous.txt'))
                gamelog.write_text('[2026-11-20 10:05:00] AppID 1 adding PID 5000 as a tracked process\n')
                wait(lambda: registered() == ['4242', '4243', '5000'])
                self.assertIn('busctl --user call com.feralinteractive.GameMode /com/feralinteractive/GameMode '
                              'com.feralinteractive.GameMode RegisterGameByPID ii', log.read_text())
            finally:
                steam.kill()
                steam.wait()
            # The watcher ends with Steam.
            wait(lambda: not watchers(client))
            # Opt-out: no watcher while Steam runs.
            steam = subprocess.Popen([bash, str(wrapper)], env={**env, 'AURORA_STEAM_GAMEMODE': '0'},
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                wait(lambda: (Path('/proc') / str(steam.pid) / 'cmdline').read_bytes().startswith(b'sleep'))
                time.sleep(0.5)
                self.assertEqual(watchers(client), [])
            finally:
                steam.kill()
                steam.wait()
            self.assertEqual(registered(), ['4242', '4243', '5000'])
    def test_touch_id_security_key_is_installed_off(self):
        text = (ROOT / 'packages/aurora-fido/aurora-fido.spec').read_text()
        files = text.split('%files', 1)[1]
        # The upstream preset says "disable aurora-fido.service"; nothing here enables it.
        self.assertIn('%{_presetdir}/90-aurora-fido.preset', files)
        self.assertIn('%systemd_post aurora-fido.service', text)
        self.assertNotRegex(text, r'systemctl\s+(--now\s+)?enable')
        self.assertIn('%config(noreplace) %{_sysconfdir}/aurora-fido/aurora-fido.conf', files)
        pins = json.loads((ROOT / 'sources.json').read_text())
        self.assertIn(pins['aurora-fido']['commit'], text)
    def test_secure_enclave_ssh_provider_gives_the_sep_key_group_the_node(self):
        text = (ROOT / 'packages/aurora-sep-sk/aurora-sep-sk.spec').read_text()
        files = text.split('%files', 1)[1]
        self.assertIn('%{_libdir}/libaurora-sep-sk.so', files)
        self.assertIn('%{_udevrulesdir}/70-aurora-sep-key.rules', files)
        self.assertIn('%{_sysusersdir}/aurora-sep-key.conf', files)
        self.assertIn('make -C sk check', text.split('%check', 1)[1].split('%install', 1)[0])
        pins = json.loads((ROOT / 'sources.json').read_text())
        self.assertIn(pins['aurora-sep-sk']['commit'], text)
    def test_camera_denoise_user_unit_skips_root_and_system_users(self):
        # camera-denoise#8 (ConditionUser, start limits) is in the pinned
        # commit and %check runs its unit test (tests/check-unit.sh).
        spec = (ROOT / 'packages/aurora-camera-denoise/aurora-camera-denoise.spec').read_text()
        pins = json.loads((ROOT / 'sources.json').read_text())
        self.assertIn(pins['aurora-camera-denoise']['commit'], spec)
        self.assertNotEqual(pins['aurora-camera-denoise']['commit'],
                            '456c567527d6bbba27d0aaeec1199032e0ec88c3')
        self.assertIn('%meson_test', spec.split('%check', 1)[1].split('%install', 1)[0])
    def test_camera_denoise_ships_the_encoder_filter_plugin(self):
        spec = (ROOT / 'packages/aurora-camera-denoise/aurora-camera-denoise.spec').read_text()
        files = spec.split('%files', 1)[1].split('%changelog', 1)[0]
        self.assertIn('%{_libdir}/aurora-camera-denoise/cdn-backend-ave.so', files)
        self.assertIn('%{_libdir}/aurora-camera-denoise/cdn-backend-ane.so', files)
        self.assertIn('%{_datadir}/aurora-camera-denoise/', files)
    def test_diagnostics_are_opt_in_and_follow_their_pin(self):
        text = (ROOT / 'packages/aurora-diag/aurora-diag.spec').read_text()
        pin = json.loads((ROOT / 'sources.json').read_text())['aurora-diag']
        self.assertIn('%global commit ' + pin['commit'] + '\n', text)
        self.assertRegex(text, r'(?m)^Version: ' + re.escape(pin['version']) + '$')
        self.assertEqual(pin['archive_root'], 'aurora-diag-' + pin['commit'])
        self.assertIn('make check', text.split('%check', 1)[1].split('%install', 1)[0])
        files = text.split('%files', 1)[1]
        for path in ('%{_bindir}/aurora-diag', '%{_bindir}/aurora-panic-log', '%{_datadir}/aurora-diag'):
            self.assertIn(path, files)
        self.assertRegex(text, r'(?m)^Requires: python3$')
        for spec in (ROOT / 'packages').glob('*/*.spec'):
            if spec.parent.name != 'aurora-diag':
                self.assertNotRegex(spec.read_text(), r'(?m)^(Requires|Recommends|Supplements)(\(\w+\))?:.*\baurora-diag\b', spec.name)
        self.assertNotIn('"aurora-diag"', (ROOT / 'images/configure.py').read_text())
if __name__ == '__main__': unittest.main()
