from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/check-basics.py'
BOOT = '2025cecd-807c-5835-9ad4-e547cfdeb279'
PREAMBLE = '# Aurora: look for this installation only on the disk GRUB started from.\n'
MESA = 'c208afc352e9d4c10ee71c883a369a9079dd7d84'


def write(path, text='', mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text)
    if mode:
        path.chmod(mode)


def link(path, target):
    path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, path)


# Touch ID as Aurora ships it: fingerprint for sudo, polkit and the lock
# screen, the password everywhere else; a short power-button press suspends.
GUARD = 'auth [success=1 default=ignore] pam_succeed_if.so service notin sudo:sudo-i:polkit-1 quiet\n'
SYSTEM_AUTH = ('auth required pam_env.so\n' + GUARD + 'auth sufficient pam_fprintd.so\n'
               'auth sufficient pam_unix.so nullok\nauth required pam_deny.so\n')
PASSWORD_AUTH = 'auth required pam_env.so\nauth sufficient pam_unix.so nullok\nauth required pam_deny.so\n'
FINGERPRINT_AUTH = 'auth [success=done default=bad] pam_fprintd.so\nauth required pam_deny.so\n'
LOGIND = '[Login]\nHandlePowerKey=suspend\nHandlePowerKeyLongPress=poweroff\n'
POWERDEVIL = ''.join(f'[{group}][SuspendAndShutdown]\nPowerButtonAction=1\n'
                     for group in ('AC', 'Battery', 'LowBattery'))


def touchid_files(etc, profile, system_auth=SYSTEM_AUTH):
    pam = etc / 'pam.d'
    write(pam / 'system-auth', system_auth)
    write(pam / 'password-auth', PASSWORD_AUTH)
    write(pam / 'fingerprint-auth', FINGERPRINT_AUTH)
    for name in ('sudo', 'polkit-1'):
        write(pam / name, 'auth include system-auth\n')
    for name in ('login', 'su'):
        write(pam / name, 'auth substack system-auth\n')
    write(pam / 'sshd', 'auth substack password-auth\n')
    services = {'gnome': {'gdm-fingerprint': 'fingerprint-auth', 'gdm-password': 'password-auth'},
                'kde': {'kde-fingerprint': 'fingerprint-auth', 'kde': 'password-auth',
                        'plasmalogin': 'password-auth'}}
    for name, stack in services.get(profile, {}).items():
        write(pam / name, f'auth substack {stack}\n')
    write(etc / 'systemd/logind.conf.d/50-aurora-sep.conf', LOGIND)
    if profile == 'kde':
        write(etc / 'xdg/powerdevilrc', POWERDEVIL)


class CheckBasicsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def fresh(self):
        self.temporary.cleanup()
        self.setUp()

    def tearDown(self):
        self.temporary.cleanup()

    def check(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPT), *arguments], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)

    def desktop_root(self, profile, usr='usr', etc='etc'):
        root = self.base / 'root'
        u, e = root / usr, root / etc
        write(e / 'locale.conf', 'LANG=en_US.UTF-8\n')
        write(root / 'usr/lib/locale/locale-archive', b'\0en_US.utf8\0')
        link(e / 'systemd/system/multi-user.target.wants/NetworkManager.service',
             '/usr/lib/systemd/system/NetworkManager.service')
        touchid_files(e, profile)
        if profile == 'gnome':
            write(u / 'bin/kgx', mode=0o755)
            write(u / 'share/applications/org.gnome.Console.desktop')
            write(u / 'bin/gnome-control-center', mode=0o755)
            write(u / 'share/backgrounds/gnome/adwaita-l.jxl')
            write(u / 'share/glib-2.0/schemas/org.gnome.desktop.background.gschema.xml',
                  "<key name=\"picture-uri\" type=\"s\">\n<default>'file:///usr/share/backgrounds/gnome/adwaita-l.jxl'</default>")
        if profile == 'kde':
            write(u / 'bin/konsole', mode=0o755)
            write(u / 'share/applications/org.kde.konsole.desktop')
            write(u / 'share/applications/kcm_networkmanagement.desktop')
            for name in ('Next', 'Air', 'Horos', 'Altai', 'Kokkini', 'Canopee', 'Cluster', 'Flow', 'Mountain'):
                write(u / f'share/wallpapers/{name}/contents/images/1920x1080.png')
        return root

    def boot(self):
        esp, boot = self.base / 'esp', self.base / 'boot'
        write(esp / 'EFI/BOOT/BOOTAA64.EFI', b'MZ\0/EFI/BOOT\0')
        write(esp / 'EFI/BOOT/grub.cfg', PREAMBLE + f'probe --set=aurora_uuid --fs-uuid "($aurora_disk,gpt$n)"\n'
              f'  search --no-floppy --fs-uuid --set=root --hint="$aurora_boot" {BOOT}\n')
        write(boot / 'grub/grub.cfg', f'search --no-floppy --fs-uuid --set=root --hint="${{aurora_disk}}," {BOOT}\n')
        return ['--esp', str(esp), '--boot-dir', str(boot), '--boot-uuid', BOOT]

    def test_complete_images_pass(self):
        for profile in ('gnome', 'kde', 'minimal'):
            with self.subTest(profile=profile):
                root = self.desktop_root(profile)
                result = self.check('--profile', profile, '--root', str(root), *self.boot())
                self.assertEqual(result.returncode, 0, result.stdout)
                self.temporary.cleanup()
                self.temporary = tempfile.TemporaryDirectory()
                self.base = Path(self.temporary.name)

    def assert_fails(self, profile, mutate, expected):
        root = self.desktop_root(profile)
        boot = self.boot()
        mutate(root)
        result = self.check('--profile', profile, '--root', str(root), *boot)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(expected, result.stdout)

    def test_global_gl_selector_fails(self):
        self.assert_fails('gnome', lambda root: write(root / 'etc/environment',
                          'MESA_LOADER_DRIVER_OVERRIDE="zink"\n'), 'global MESA_LOADER_DRIVER_OVERRIDE')

    def test_global_gallium_environment_d_fails(self):
        self.assert_fails('minimal', lambda root: write(root / 'usr/lib/environment.d/90-gl.conf',
                          "export GALLIUM_DRIVER='zink'\n"), 'global GALLIUM_DRIVER')

    def test_no_gl_selector_or_empty_value_passes(self):
        root = self.desktop_root('gnome')
        write(root / 'etc/environment', '# MESA_LOADER_DRIVER_OVERRIDE=zink\nLANG=en_US.UTF-8\n')
        write(root / 'etc/environment.d/90-gl.conf', 'GALLIUM_DRIVER=""\n')
        result = self.check('--profile', 'gnome', '--root', str(root))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_nixos_session_gl_selector_fails(self):
        self.assert_fails('gnome', lambda root: write(root / 'etc/set-environment',
                          'export MESA_LOADER_DRIVER_OVERRIDE=zink\n'), 'global MESA_LOADER_DRIVER_OVERRIDE')

    def test_c_locale_fails(self):
        self.assert_fails('gnome', lambda root: write(root / 'etc/locale.conf', 'LANG=C\n'), 'locale: FAIL')

    def test_ungenerated_locale_fails(self):
        self.assert_fails('minimal', lambda root: write(root / 'usr/lib/locale/locale-archive', b'\0de_DE.utf8\0'),
                          'is not generated')

    def test_missing_terminal_fails(self):
        self.assert_fails('kde', lambda root: (root / 'usr/bin/konsole').unlink(), 'terminal: FAIL')

    def test_missing_gnome_backgrounds_fails(self):
        self.assert_fails('gnome', lambda root: (root / 'usr/share/backgrounds/gnome/adwaita-l.jxl').unlink(),
                          'gnome-backgrounds')

    def test_default_gnome_picture_must_exist(self):
        def mutate(root):
            write(root / 'usr/share/glib-2.0/schemas/10_vendor.gschema.override',
                  "[org.gnome.desktop.background]\npicture-uri='file:///usr/share/backgrounds/vendor/missing.png'\n")
        self.assert_fails('gnome', mutate, 'does not exist')

    def test_missing_plasma_wallpapers_fails(self):
        def mutate(root):
            # What plasma-workspace alone ships: Next, Air and Horos.
            for name in ('Altai', 'Kokkini', 'Canopee', 'Cluster', 'Flow', 'Mountain'):
                (root / f'usr/share/wallpapers/{name}/contents/images/1920x1080.png').unlink()
        self.assert_fails('kde', mutate, 'plasma-workspace-wallpapers')

    def test_disabled_networkmanager_fails(self):
        self.assert_fails('minimal', lambda root: (
            root / 'etc/systemd/system/multi-user.target.wants/NetworkManager.service').unlink(), 'network: FAIL')

    def test_lid_policy_and_masked_sleep_fail(self):
        self.assert_fails('minimal', lambda root: write(root / 'etc/systemd/logind.conf.d/10-lid.conf',
                                                         '[Login]\nHandleLidSwitch=ignore\n'), 'HandleLidSwitch=ignore')
        self.temporary.cleanup()
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.assert_fails('minimal', lambda root: link(root / 'etc/systemd/system/suspend.target', '/dev/null'),
                          'suspend.target is masked')

    def test_executable_unit_or_drop_in_fails(self):
        for name in ('usr/lib/systemd/system/example.path',
                     'usr/lib/systemd/user/drkonqi-sentry-postman.path.d/50-aurora-ordering.conf',
                     'etc/systemd/system/example.service'):
            with self.subTest(name=name):
                self.assert_fails('minimal', lambda root: write(root / name, '[Unit]\n', mode=0o755),
                                  f'/{name} is marked executable')
                self.temporary.cleanup()
                self.temporary = tempfile.TemporaryDirectory()
                self.base = Path(self.temporary.name)

    def test_plain_units_and_drop_ins_pass(self):
        root = self.desktop_root('minimal')
        write(root / 'usr/lib/systemd/system/example.service', '[Service]\n', mode=0o644)
        write(root / 'usr/lib/systemd/system/example.service.d/50-example.conf', '[Unit]\n', mode=0o644)
        result = self.check('--profile', 'minimal', '--root', str(root))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('units: ok', result.stdout)

    def test_core_with_an_early_uuid_search_fails(self):
        self.assert_fails('minimal', lambda root: write(self.base / 'esp/EFI/BOOT/BOOTAA64.EFI',
                                                         f'MZ\0/EFI/BOOT\0search.fs_uuid {BOOT} root\0'.encode()),
                          'all-disk search')

    def test_partition_numbered_core_fails(self):
        self.assert_fails('minimal', lambda root: write(self.base / 'esp/EFI/BOOT/BOOTAA64.EFI',
                                                         b'MZ\0(,gpt2)/grub\0'), 'partition number')

    def test_unhinted_search_fails(self):
        self.assert_fails('minimal', lambda root: write(self.base / 'boot/grub/grub.cfg',
                                                         f'search --no-floppy --fs-uuid --set=root {BOOT}\n'),
                          'without a hint')

    def test_stub_must_name_the_boot_uuid(self):
        self.assert_fails('minimal', lambda root: write(self.base / 'esp/EFI/BOOT/grub.cfg', PREAMBLE),
                          'by UUID on the startup disk')

    def test_nixos_system_closure_is_read_through_store_links(self):
        root = self.base / 'root'
        system = '/nix/store/aaaa-nixos-system'
        sw = '/nix/store/bbbb-system-path'
        etc = '/nix/store/cccc-etc/etc'
        link(root / system.lstrip('/') / 'sw', sw)
        link(root / system.lstrip('/') / 'etc', etc)
        write(root / etc.lstrip('/') / 'locale.conf', 'LANG=en_US.UTF-8\n')
        write(root / etc.lstrip('/') / 'set-environment',
              'export LOCALE_ARCHIVE="/nix/store/dddd-glibc-locales/lib/locale/locale-archive"\n')
        write(root / 'nix/store/dddd-glibc-locales/lib/locale/locale-archive', b'\0en_US.utf8\0')
        link(root / etc.lstrip('/') / 'systemd/system/multi-user.target.wants/NetworkManager.service',
             '/nix/store/eeee-unit/NetworkManager.service')
        write(root / sw.lstrip('/') / 'bin/kgx', mode=0o755)
        write(root / sw.lstrip('/') / 'share/applications/org.gnome.Console.desktop')
        write(root / sw.lstrip('/') / 'bin/gnome-control-center', mode=0o755)
        write(root / sw.lstrip('/') / 'share/backgrounds/gnome/adwaita-l.jxl')
        touchid_files(root / etc.lstrip('/'), 'gnome')
        result = self.check('--profile', 'gnome', '--root', str(root), '--system', system, *self.boot())
        self.assertEqual(result.returncode, 0, result.stdout)
        write(root / etc.lstrip('/') / 'locale.conf', 'LANG=C\n')
        self.assertNotEqual(self.check('--profile', 'gnome', '--root', str(root), '--system', system).returncode, 0)

    def test_fingerprint_at_the_console_login_and_su_fails(self):
        def mutate(root):
            write(root / 'etc/pam.d/system-auth', SYSTEM_AUTH.replace(GUARD, ''))
        self.assert_fails('minimal', mutate, 'login offers a fingerprint; su offers a fingerprint')

    def test_sudo_and_polkit_without_fingerprint_fail(self):
        def mutate(root):
            write(root / 'etc/pam.d/system-auth', PASSWORD_AUTH)
        self.assert_fails('gnome', mutate, 'sudo does not offer a fingerprint; polkit-1 does not offer a fingerprint')

    def test_fingerprint_that_replaces_the_password_fails(self):
        def mutate(root):
            write(root / 'etc/pam.d/sudo', 'auth required pam_fprintd.so\nauth include system-auth\n')
        self.assert_fails('minimal', mutate, 'sudo has no password after the fingerprint')

    def test_fingerprint_at_the_login_screen_fails(self):
        def mutate(root):
            write(root / 'etc/pam.d/plasmalogin', 'auth substack system-auth\n')
            write(root / 'etc/pam.d/system-auth', SYSTEM_AUTH.replace('notin sudo:', 'notin plasmalogin:sudo:'))
        self.assert_fails('kde', mutate, 'plasmalogin offers a fingerprint')

    def test_lock_screen_without_fingerprint_fails(self):
        self.assert_fails('gnome', lambda root: write(root / 'etc/pam.d/fingerprint-auth', PASSWORD_AUTH),
                          'gdm-fingerprint does not offer a fingerprint')

    def test_vendor_pam_directory_is_read(self):
        def mutate(root):
            (root / 'etc/pam.d/polkit-1').unlink()
            write(root / 'usr/lib/pam.d/polkit-1', 'auth required pam_unix.so\n')
        self.assert_fails('minimal', mutate, 'polkit-1 does not offer a fingerprint')

    def test_authselect_profile_is_checked_with_fingerprint_on(self):
        stock = ('auth required pam_env.so\n'
                 'auth sufficient pam_fprintd.so {include if "with-fingerprint"}\n'
                 'auth sufficient pam_unix.so {if not "without-nullok":nullok}\nauth required pam_deny.so\n')
        vendor = stock.replace('auth sufficient pam_fprintd.so', GUARD.rstrip('\n') +
                               ' {include if "with-fingerprint"}\nauth sufficient pam_fprintd.so')
        fingerprint = ('auth required pam_debug.so auth=authinfo_unavail {exclude if "with-fingerprint"}\n'
                       '{continue if "with-fingerprint"}\n' + FINGERPRINT_AUTH)

        def profile(root, system_auth):
            write(root / 'etc/authselect/authselect.conf', 'local\nwith-silent-lastlog\n')
            for name, text in (('system-auth', system_auth), ('password-auth', PASSWORD_AUTH),
                               ('fingerprint-auth', fingerprint)):
                write(root / f'usr/share/authselect/vendor/local/{name}', text)
                # What authselect wrote with the feature still off.
                write(root / f'etc/authselect/{name}', PASSWORD_AUTH if name != 'fingerprint-auth' else
                      'auth required pam_debug.so auth=authinfo_unavail\n')
                (root / f'etc/pam.d/{name}').unlink()
                link(root / f'etc/pam.d/{name}', f'/etc/authselect/{name}')

        root = self.desktop_root('gnome')
        profile(root, vendor)
        result = self.check('--profile', 'gnome', '--root', str(root))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.fresh()
        root = self.desktop_root('gnome')
        profile(root, stock)
        result = self.check('--profile', 'gnome', '--root', str(root))
        self.assertIn('login offers a fingerprint', result.stdout)

    def test_power_key_that_powers_off_fails(self):
        self.assert_fails('minimal', lambda root: (root / 'etc/systemd/logind.conf.d/50-aurora-sep.conf').unlink(),
                          'logind HandlePowerKey=(default), not suspend')
        self.fresh()
        self.assert_fails('gnome', lambda root: write(root / 'etc/systemd/logind.conf.d/90-local.conf',
                          '[Login]\nHandlePowerKey=poweroff\n'), 'logind HandlePowerKey=poweroff, not suspend')

    def test_plasma_power_button_must_suspend(self):
        self.assert_fails('kde', lambda root: (root / 'etc/xdg/powerdevilrc').unlink(),
                          'Plasma AC power button action is the logout screen, not suspend')

    def flatpak_gl(self, root, commit=MESA, host=MESA, branches=('25.08', '26.08')):
        """A root with the host Mesa and GL.aurora as aurora-flatpak-gl installs it."""
        write(root / 'usr/lib64/libgallium-26.3.0-devel.so', f'\0Mesa 26.3.0-devel (git-{host[:10]})\0'.encode())
        for branch in branches:
            ref = root / f'var/lib/flatpak/runtime/org.freedesktop.Platform.GL.aurora/aarch64/{branch}'
            write(ref / f'deploy{branch}/files/.aurora-mesa-commit', commit + '\n')
            link(ref / 'active', f'deploy{branch}')
        write(root / 'usr/lib/environment.d/60-aurora-flatpak-gl.conf',
              'FLATPAK_GL_DRIVERS=${FLATPAK_GL_DRIVERS:-aurora:default:host}\n')
        write(root / 'var/lib/flatpak/overrides/global',
              '[Environment]\nVK_DRIVER_FILES=/usr/lib/aarch64-linux-gnu/GL/vulkan/icd.d/asahi_icd.aarch64.json\n')
        return root

    def check_flatpak_gl(self, root):
        return self.check('--profile', 'kde', '--root', str(root), '--flatpak-gl')

    def test_flatpak_gl_from_the_host_mesa_passes(self):
        result = self.check_flatpak_gl(self.flatpak_gl(self.desktop_root('kde')))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('flatpak-gl: ok', result.stdout)

    def test_flatpak_gl_is_only_required_when_asked(self):
        result = self.check('--profile', 'kde', '--root', str(self.desktop_root('kde')))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn('flatpak-gl', result.stdout)

    def assert_flatpak_gl_fails(self, root, expected):
        result = self.check_flatpak_gl(root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(expected, result.stdout)

    def test_missing_flatpak_gl_branch_fails(self):
        self.assert_flatpak_gl_fails(self.flatpak_gl(self.desktop_root('kde'), branches=('25.08',)),
                                     'GL.aurora/aarch64/26.08 is not installed')

    def test_flatpak_gl_from_another_mesa_fails(self):
        root = self.flatpak_gl(self.desktop_root('kde'), host='473e325b4f50' + MESA[12:])
        self.assert_flatpak_gl_fails(root, 'not the host Mesa')

    def test_unselected_flatpak_gl_fails(self):
        root = self.flatpak_gl(self.desktop_root('kde'))
        (root / 'usr/lib/environment.d/60-aurora-flatpak-gl.conf').unlink()
        self.assert_flatpak_gl_fails(root, 'FLATPAK_GL_DRIVERS does not select GL.aurora')

    def test_missing_flatpak_override_fails(self):
        root = self.flatpak_gl(self.desktop_root('kde'))
        (root / 'var/lib/flatpak/overrides/global').unlink()
        self.assert_flatpak_gl_fails(root, 'system Flatpak override')


if __name__ == '__main__':
    unittest.main()
