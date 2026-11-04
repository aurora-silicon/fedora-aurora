import configparser
import json
from pathlib import Path
import os
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
class SpecTests(unittest.TestCase):
    def test_declared_local_sources_and_patches_are_present(self):
        pins = json.loads((ROOT / 'sources.json').read_text())
        for spec in (ROOT / 'packages').glob('*/*.spec'):
            extras = pins.get(spec.parent.name, {}).get('extra_sources', {})
            fetched = {record.get("archive_file", f"{name}-{record['commit']}.tar.gz") for name, record in extras.items()}
            with self.subTest(spec=spec.name):
                for kind, value in re.findall(r'^(Source\d*|Patch\d*):\s+(\S+)', spec.read_text(), re.M):
                    if '%{' not in value and not value.startswith('http') and value not in fetched:
                        self.assertTrue((spec.parent / value).is_file(), value)
    def test_noarch_recipes_do_not_claim_machine_specific_binaries(self):
        for name in ['aurora-audio', 'alsa-ucm-conf-aurora', 'aurora-release', 'aurora-repos', 'aurora-logos', 'speakersafetyd-aurora-profiles']:
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
        # hook coldplugs it (and its suppliers) ahead of systemd-udev-trigger.
        d = ROOT / 'packages' / 'aurora-platform'
        setup = (d / 'early-kms-module-setup.sh').read_text()
        self.assertRegex(setup, r"(?m)^\s+hostonly='' instmods appledrm$")
        self.assertRegex(setup, r'(?m)^\s+inst_hook pre-trigger \d+ "\$moddir/aurora-early-kms\.sh"$')
        hook = (d / 'aurora-early-kms.sh').read_text()
        self.assertIn("*Capple,display-subsystem*|*Capple,dcp*)", hook)
        self.assertIn('supplier:*', hook)
        self.assertIn('udevadm trigger --action=add --subsystem-match=drm --settle', hook)
        self.assertNotRegex(hook, r'(?m)^\s*modprobe ')
        subprocess.run(['sh', '-n', str(d / 'aurora-early-kms.sh')], check=True)
        text = (d / 'aurora-platform.spec').read_text()
        self.assertRegex(text, r'(?m)^Source\d+: early-kms-module-setup\.sh$')
        self.assertRegex(text, r'(?m)^Source\d+: aurora-early-kms\.sh$')
        self.assertIn('/lib/dracut/modules.d/91aurora-early-kms/module-setup.sh', text)
        self.assertIn('/lib/dracut/modules.d/91aurora-early-kms/aurora-early-kms.sh', text)
        core_files = text.split('%files core', 1)[1].split('%changelog', 1)[0]
        self.assertIn('%{_prefix}/lib/dracut/modules.d/91aurora-early-kms/', core_files)
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
    def test_platform_core_carries_no_kernel_or_boot_chain(self):
        d = ROOT / 'packages' / 'aurora-platform'
        text = (d / 'aurora-platform.spec').read_text()
        core = text.split('%package core', 1)[1].split('%description core', 1)[0]
        requires = ' '.join(re.findall(r'^Requires:\s+(.+)$', core, re.M)).split()
        for name in ['update-m1n1', 'dracut-asahi', 'asahi-fwupdate',
                     'aurora-audio', 'alsa-ucm-conf-aurora', 'aurora-camera-denoise']:
            self.assertIn(name, requires)
        # Speaker protection: the current daemons, or the speakerguardd 1.0
        # opt-in in their place; dnf picks the recommended current ones.
        for name in ['speakersafetyd', 'speakerguardd']:
            self.assertRegex(core, r'(?m)^Requires: \(' + name + r' or speakerguardd-v2-replace-legacy\)$')
        self.assertRegex(core, r'(?m)^Recommends: speakersafetyd speakerguardd$')
        for name in requires:
            self.assertFalse(name.startswith(('kernel', 'uboot', 'm1n1')) or name == 'aura', name)
        self.assertNotIn('aurora-release', requires)
        self.assertNotIn('aurora-bless', requires)
        for name in ['asahi-platform-metapackage', 'asahi-platform-metapackage-core']:
            self.assertRegex(core, r'(?m)^Obsoletes: ' + name + r' < 1$')
        self.assertEqual((d / 'aurora-platform-core.conf').read_text().split(), ['aurora-platform-core'])
        self.assertIn('protected.d/aurora-platform-core.conf', text.split('%files core', 1)[1])
        self.assertRegex(text, r'(?m)^Requires: aurora-platform-core = %\{version\}-%\{release\}$')
    def test_speakerguardd_v2_is_parallel_and_opt_in(self):
        d = ROOT / 'packages' / 'speakerguardd-v2'
        text = (d / 'speakerguardd-v2.spec').read_text()
        main = text.split('%package selinux', 1)[0]
        optin = text.split('%package replace-legacy', 1)[1].split('%description replace-legacy', 1)[0]
        # The preview installs beside the 0.1 daemon and speakersafetyd.
        self.assertNotRegex(main, r'(?m)^(Conflicts|Obsoletes|Provides):')
        self.assertIn('%{_libexecdir}/speakerguardd-v2/speakerguardd', text)
        self.assertIn('%{_unitdir}/speakerguardd-v2.service', text)
        self.assertIn('%{_libdir}/lv2/sgv2.lv2/', text)
        # Only the clearly named opt-in conflicts with them. It never obsoletes
        # or provides them, so dnf cannot choose it on its own.
        self.assertRegex(optin, r'(?m)^Conflicts: speakerguardd < 1\.0\.0~$')
        self.assertRegex(optin, r'(?m)^Conflicts: speakersafetyd$')
        self.assertNotRegex(optin, r'(?m)^(Obsoletes|Provides):')
        self.assertEqual((d / '50-speakerguardd-v2.preset').read_text().split('\n')[1], 'enable speakerguardd-v2.service')
        self.assertIn('%{_presetdir}/50-speakerguardd-v2.preset', text.split('%files replace-legacy', 1)[1])
        # The SELinux module labels the program where this package installs it.
        fc = (d / 'speakerguardd.fc').read_text()
        self.assertIn('/usr/libexec/speakerguardd-v2/speakerguardd\t--\tgen_context(system_u:object_r:speakerguardd_exec_t,s0)', fc)
        self.assertIn('/run/speakerguardd(/.*)?', fc)
        # aurora-audio accepts the opt-in too, and recommends the current daemons.
        audio = (ROOT / 'packages/aurora-audio/aurora-audio.spec').read_text()
        for name in ['speakersafetyd', 'speakerguardd']:
            self.assertRegex(audio, r'(?m)^Requires: \(' + name + r' or speakerguardd-v2-replace-legacy\)$')
        self.assertRegex(audio, r'(?m)^Recommends: speakersafetyd speakerguardd$')
    def test_aurora_repos_owns_the_repository_key_and_vendor_policies(self):
        d = ROOT / 'packages' / 'aurora-repos'
        spec = (d / 'aurora-repos.spec').read_text()
        self.assertEqual((d / 'RPM-GPG-KEY-aurora').read_bytes(), (ROOT / 'keys' / 'RPM-GPG-KEY-aurora').read_bytes())
        repo = (d / 'aurora.repo').read_text()
        # The installed release picks its repository, and a release without
        # one stops a refresh or upgrade instead of dropping Aurora.
        self.assertIn('baseurl=https://aurorasilicon.org/fedora-aurora/$releasever/testing/aarch64\n', repo)
        for line in ['gpgcheck=1', 'gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-aurora', 'skip_if_unavailable=False']:
            self.assertIn('\n' + line + '\n', repo)
        self.assertNotIn('repo_gpgcheck', repo)
        # Fedora 44's dnf5 cannot trust a metadata key without a prompt, and an
        # unanswered prompt skips the repository. The override also covers a
        # locally changed aurora.repo.
        override = configparser.ConfigParser(interpolation=None)
        override.read_string((d / 'aurora-override.repo').read_text())
        self.assertEqual(override.sections(), ['aurora'])
        self.assertEqual(dict(override['aurora']), {'repo_gpgcheck': '0', 'auto_import_local_keys': '1'})
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

    def run_theme_post(self, current, cmdline=None):
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
            dracut.write_text(f'#!/bin/bash\necho "$@" >> {log}\n')
            dracut.chmod(0o755)
            grubby = tmp / 'bin/grubby'
            grubby.write_text(f'#!/bin/bash\necho "$@" >> {tmp / "grubby.log"}\n')
            grubby.chmod(0o755)
            if cmdline is not None:
                (tmp / 'etc/kernel').mkdir()
                (tmp / 'etc/kernel/cmdline').write_text(cmdline + '\n')
            def render(script):
                return (script.replace('%{_bindir}', str(tmp / 'bin')).replace('%{_sbindir}', str(tmp / 'bin'))
                        .replace('%{_sysconfdir}', str(tmp / 'etc'))
                        .replace('%{_localstatedir}', str(tmp / 'var')).replace('/run/systemd/system', str(tmp)))
            env = dict(os.environ, PATH=f"{tmp / 'bin'}:{os.environ['PATH']}")
            for script in (post, posttrans):
                subprocess.run(['bash', '-euc', render(script)], check=True, env=env)
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

    def test_theme_replaces_only_a_stock_default_and_rebuilds_the_initramfs(self):
        for stock in ('', 'bgrt', 'spinner', 'charge'):
            theme, dracut = self.run_theme_post(stock)
            self.assertEqual(theme, 'aurora', stock)
            self.assertEqual(dracut.strip(), '-f --regenerate-all', stock)

    def test_theme_keeps_the_owners_choice(self):
        for chosen in ('solar', 'details', 'aurora'):
            theme, dracut = self.run_theme_post(chosen)
            self.assertEqual(theme, chosen)
            self.assertEqual(dracut, '')

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
        for requirement in ('aurora-userpages', 'fex-emu', 'gtk2'):
            self.assertRegex(spec, rf'(?m)^Requires: {requirement}$')
        # Fedora installs the launcher on PATH, not where the upstream default looks.
        self.assertIn("s,@USERPAGES@,%{_bindir}/userpages,", spec)
        wrapper = (d / 'steam').read_text()
        self.assertIn('userpages=${AURORA_USERPAGES_LAUNCHER:-@USERPAGES@}\nexport AURORA_USERPAGES_LAUNCHER=$userpages\n', wrapper)
        self.assertIn('"$userpages" 4k true', wrapper)
        self.assertIn('exec "$lib/bin/steam-native4k" "$@"', wrapper)
        subprocess.run(['bash', '-n', str(d / 'steam')], check=True)

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
if __name__ == '__main__': unittest.main()
