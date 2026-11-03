import configparser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
class SpecTests(unittest.TestCase):
    def test_declared_local_sources_and_patches_are_present(self):
        pins = json.loads((ROOT / 'sources.json').read_text())
        for spec in (ROOT / 'packages').glob('*/*.spec'):
            extras = pins.get(spec.parent.name, {}).get('extra_sources', {})
            fetched = {f"{name}-{record['commit']}.tar.gz" for name, record in extras.items()}
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
        for name in ['update-m1n1', 'dracut-asahi', 'asahi-fwupdate', 'speakersafetyd',
                     'speakerguardd', 'aurora-audio', 'alsa-ucm-conf-aurora', 'aurora-camera-denoise']:
            self.assertIn(name, requires)
        for name in requires:
            self.assertFalse(name.startswith(('kernel', 'uboot', 'm1n1')) or name == 'aura', name)
        self.assertNotIn('aurora-release', requires)
        self.assertNotIn('aurora-bless', requires)
        for name in ['asahi-platform-metapackage', 'asahi-platform-metapackage-core']:
            self.assertRegex(core, r'(?m)^Obsoletes: ' + name + r' < 1$')
        self.assertEqual((d / 'aurora-platform-core.conf').read_text().split(), ['aurora-platform-core'])
        self.assertIn('protected.d/aurora-platform-core.conf', text.split('%files core', 1)[1])
        self.assertRegex(text, r'(?m)^Requires: aurora-platform-core = %\{version\}-%\{release\}$')
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
if __name__ == '__main__': unittest.main()
