from pathlib import Path
import os
import shutil
import struct
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


def grub_core(*modules):
    """A GRUB EFI core image whose module area holds these modules."""
    objects = b''
    for name in modules:
        strings, modname = b'\0.shstrtab\0.modname\0', name.encode() + b'\0'
        elf = bytearray(64)
        elf[:4] = b'\x7fELF'
        struct.pack_into('<Q', elf, 0x28, 64 + len(strings) + len(modname))
        struct.pack_into('<HHH', elf, 0x3a, 64, 3, 1)
        elf += strings + modname + bytes(64)
        elf += struct.pack('<IIQQQQ', 1, 3, 0, 0, 64, len(strings)) + bytes(24)
        elf += struct.pack('<IIQQQQ', strings.index(b'.modname'), 1, 0, 0, 64 + len(strings),
                           len(modname)) + bytes(24)
        objects += struct.pack('<II', 0, 8 + len(elf)) + elf
    return b'MZ\0/EFI/BOOT\0' + struct.pack('<4sIQQ', b'mimg', 0, 24, 24 + len(objects)) + objects


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

    # The video lines nixpkgs' install-grub.pl writes for every EFI GRUB (the
    # NixOS images' "efi_uga.mod not found").
    NIXOS_VIDEO = ('if [ "${grub_platform}" = "efi" ]; then\n  insmod efi_gop\n  insmod efi_uga\n'
                   'else\n  insmod vbe\nfi\n')

    def grub(self, main, modules=('efi_gop',), files=(), core=None):
        """Check a /boot/grub/grub.cfg with these arm64-efi modules and /boot files."""
        arguments = self.boot()
        write(self.base / 'boot/grub/grub.cfg',
              f'search --no-floppy --fs-uuid --set=root --hint="${{aurora_disk}}," {BOOT}\n' + main)
        for name in modules:
            write(self.base / f'boot/grub/arm64-efi/{name}.mod')
        for name in files:
            write(self.base / 'boot' / name)
        if core is not None:
            write(self.base / 'esp/EFI/BOOT/BOOTAA64.EFI', grub_core(*core))
        return self.check('--profile', 'minimal', *arguments, '--efi-uuid', '1E08-14ED')

    def assert_grub_fails(self, expected, *arguments, **options):
        result = self.grub(*arguments, **options)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(expected, result.stdout)
        self.fresh()

    def assert_grub_passes(self, *arguments, **options):
        result = self.grub(*arguments, **options)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.fresh()

    def test_grub_module_missing_from_arm64_efi_fails(self):
        self.assert_grub_fails('insmod efi_uga: /grub/arm64-efi/efi_uga.mod is not on the boot filesystem',
                               self.NIXOS_VIDEO)
        self.assert_grub_passes(self.NIXOS_VIDEO.replace('  insmod efi_uga\n', ''))

    def test_grub_module_in_a_condition_fails(self):
        self.assert_grub_fails('insmod efi_uga', 'if insmod efi_uga; then\n  echo video\nfi\n')

    def test_grub_module_built_into_the_core_passes(self):
        self.assert_grub_passes('insmod regexp\n', modules=(), core=('normal', 'regexp'))
        self.assert_grub_fails('insmod regexp', 'insmod regexp\n', modules=(), core=('normal',))

    def test_grub_feature_fallback_is_not_checked(self):
        load_video = ('function load_video {\n  if [ x$feature_all_video_module = xy ]; then\n'
                      '    insmod all_video\n  else\n    insmod efi_uga\n    insmod vbe\n  fi\n}\n')
        self.assert_grub_passes(load_video, modules=('all_video',))
        self.assert_grub_fails('insmod all_video', load_video, modules=())

    def test_grub_fonts_kernels_and_initrds_must_exist(self):
        main = ('insmod font\nif loadfont unicode; then\n  insmod gfxterm\nfi\n'
                'menuentry "NixOS" --class nixos {\n'
                f'search --no-floppy --fs-uuid --set=drive1 --hint="${{aurora_disk}}," {BOOT}\n'
                '  linux ($drive1)//kernels/a-Image init=/nix/store/b/init\n'
                '  initrd ($drive1)//kernels/c-initrd\n}\n')
        files = ('grub/fonts/unicode.pf2', 'kernels/a-Image', 'kernels/c-initrd')
        modules = ('font', 'gfxterm')
        self.assert_grub_passes(main, modules=modules, files=files)
        self.assert_grub_fails('loadfont unicode: /grub/fonts/unicode.pf2', main, modules=modules,
                               files=files[1:])
        self.assert_grub_fails('initrd: /kernels/c-initrd', main, modules=modules, files=files[:2])

    def test_grub_search_for_a_filesystem_outside_the_image_fails(self):
        self.assert_grub_fails('no filesystem in the image has the UUID 0bad-c0de',
                               'search --no-floppy --fs-uuid --set=esp --hint="${aurora_disk}," 0bad-c0de\n')
        self.assert_grub_passes('search --no-floppy --fs-uuid --set=esp --hint="${aurora_disk}," 1E08-14ED\n')

    def test_grub_environment_block_must_exist_unless_tested(self):
        self.assert_grub_passes('if [ -s $prefix/grubenv ]; then\n  load_env\nfi\n')
        self.assert_grub_fails('save_env: /grub/grubenv', 'if [ "${next_entry}" ]; then\n  save_env next_entry\nfi\n')
        self.assert_grub_passes('if [ "${next_entry}" ]; then\n  save_env next_entry\nfi\n',
                                files=('grub/grubenv',))

    def test_grub_optional_files_tested_first_pass(self):
        self.assert_grub_passes('if [ -f  ${config_directory}/custom.cfg ]; then\n'
                                '  source ${config_directory}/custom.cfg\n'
                                'elif [ -z "${config_directory}" -a -f  $prefix/custom.cfg ]; then\n'
                                '  source $prefix/custom.cfg\nfi\n')
        self.assert_grub_fails('source: /grub/custom.cfg', 'source $prefix/custom.cfg\n')

    def test_grub_reads_the_boot_image_as_the_installer_writes_it(self):
        if not (shutil.which('mkfs.ext4') and shutil.which('debugfs')):
            self.skipTest('needs mkfs.ext4 and debugfs')
        arguments = self.boot()
        boot = self.base / 'boot'
        write(boot / 'grub/grub.cfg', f'search --no-floppy --fs-uuid --set=root --hint="${{aurora_disk}}," {BOOT}\n'
              'insmod efi_gop\nlinux /vmlinuz-linux-aurora root=UUID=x\ninitrd /initramfs-linux-aurora.img\n')
        write(boot / 'grub/arm64-efi/efi_gop.mod')
        write(boot / 'vmlinuz-linux-aurora')
        os.symlink('initramfs-real.img', boot / 'initramfs-linux-aurora.img')
        image = self.base / 'boot.img'
        index = arguments.index('--boot-dir')
        arguments[index:index + 2] = ['--boot-image', str(image)]

        def run():
            image.unlink(missing_ok=True)
            subprocess.run(['mkfs.ext4', '-q', '-F', '-d', str(boot), str(image), '4M'], check=True)
            return self.check('--profile', 'minimal', *arguments)
        result = run()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('initrd: /initramfs-linux-aurora.img is not on the boot filesystem', result.stdout)
        write(boot / 'initramfs-real.img')
        result = run()
        self.assertEqual(result.returncode, 0, result.stdout)
        (boot / 'grub/arm64-efi/efi_gop.mod').unlink()
        result = run()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('insmod efi_gop: /grub/arm64-efi/efi_gop.mod', result.stdout)

    def fedora(self, main, entries, files=(), core=('part_gpt', 'ext2', 'blscfg')):
        """Fedora's layout: signed GRUB cores with built-in modules, BLS entries."""
        esp, boot = self.base / 'esp', self.base / 'boot'
        stub = (PREAMBLE + f'if test -f "($aurora_disk,gpt1)/grub2/aurora-boot-{BOOT}"; then\n'
                '  set aurora_boot="$aurora_disk,gpt1"\nfi\n'
                f'search --no-floppy --fs-uuid --set=root --hint="$aurora_boot" {BOOT}\n'
                'set prefix=($root)/grub2\nconfigfile ($root)/grub2/grub.cfg\n')
        for directory in ('EFI/BOOT', 'EFI/fedora'):
            write(esp / directory / 'grub.cfg', stub)
            write(esp / directory / 'grubaa64.efi', grub_core(*core))
        write(boot / f'grub2/aurora-boot-{BOOT}')
        write(boot / 'grub2/grub.cfg',
              f'search --no-floppy --fs-uuid --set=root --hint="${{aurora_disk}}," {BOOT}\n' + main)
        for name, text in entries.items():
            write(boot / 'loader/entries' / name, text)
        for name in files:
            write(boot / name)
        return self.check('--profile', 'minimal', '--esp', str(esp), '--boot-dir', str(boot), '--boot-uuid', BOOT,
                          '--efi-uuid', '1E08-14ED', '--grub-flavor', 'fedora')

    def test_fedora_bls_entries_and_built_in_modules(self):
        main = ('set tuned_initrd=""\ninsmod part_gpt\ninsmod ext2\n'
                'set boot="$aurora_esp"\nif [ -z "$boot" ]; then\n'
                '  search --no-floppy --fs-uuid --set=boot --hint="${aurora_disk}," 1E08-14ED\nfi\n'
                'insmod blscfg\nblscfg\n')
        entry = {'a-7.3.0.conf': 'title Aurora\nlinux /vmlinuz-7.3.0\ninitrd /initramfs-7.3.0.img $tuned_initrd\n'
                                 'options quiet\n'}
        files = ('vmlinuz-7.3.0', 'initramfs-7.3.0.img')
        result = self.fedora(main, entry, files)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.fresh()
        result = self.fedora(main, entry, files[:1])
        self.assertIn('a-7.3.0.conf: initrd: /initramfs-7.3.0.img is not on the boot filesystem', result.stdout)
        self.fresh()
        # Fedora's /boot/grub2 has no arm64-efi directory: modules must be built in.
        result = self.fedora(main, entry, files, core=('part_gpt', 'ext2'))
        self.assertIn('insmod blscfg: /grub2/arm64-efi/blscfg.mod is not on the boot filesystem', result.stdout)

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
