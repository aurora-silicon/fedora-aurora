"""The ESP Stage 2 files an update and an image build write, per Mac.

The shipped update-m1n1 runs for real against a temporary ESP. Only the system
paths it hardcodes are redirected, as the package build does for its config
file, and the ESP mount is stubbed.
"""
import gzip
import importlib.util
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'packages/update-m1n1/update-m1n1'
SPEC = ROOT / 'packages/update-m1n1/update-m1n1.spec'

# Every chip AuraStage1Format.usesMachO admits or names, and every one below it.
MACHO_CHIPS = ('t8132', 't6040', 't6041', 't8140', 't8142', 't8152', 't6050', 't6051', 't6052', 't8130', 't8fff', 't6fff')
EARLIER_CHIPS = ('t8103', 't8112', 't8122', 't6000', 't6001', 't6002', 't6020', 't6021', 't6022', 't6030', 't6031', 't6034', 't8015')

AURA = b'AURA-STAGE2-BINARY'
UBOOT = b'u-boot payload'
FROZEN = b'frozen old aura stage 2'


def device_tree(compatibles):
    """A minimal valid flattened device tree whose root has these compatibles."""
    strings = b'compatible\0'
    value = b''.join(item.encode() + b'\0' for item in compatibles)
    padded = value + b'\0' * (-len(value) % 4)
    body = (struct.pack('>I', 1) + b'\0\0\0\0'
            + struct.pack('>III', 3, len(value), 0) + padded
            + struct.pack('>I', 2) + struct.pack('>I', 9))
    struct_offset = 40
    strings_offset = struct_offset + len(body)
    total = strings_offset + len(strings)
    header = struct.pack('>10I', 0xD00DFEED, total, struct_offset, strings_offset, 40,
                         17, 16, 0, len(strings), len(body))
    return header + body + strings


def compatible_file(board, chip):
    return f'apple,{board}\0apple,{chip}\0apple,arm-platform\0'.encode()


def load_prepare():
    spec = importlib.util.spec_from_file_location('prepare_ctxr_stage2', ROOT / 'scripts/prepare-ctxr-stage2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_ctxr = load_prepare()


class UpdateM1n1(unittest.TestCase):
    TREES = {'t8103-j274.dtb': b'dtb-j274', 't6040-j616s-tether.dtb': b'dtb-j616s-tether',
             't6040-j616s.dtb': b'dtb-j616s', 't8140-j700-ane-test.dtb': b'dtb-j700-ane',
             't8140-j700.dtb': b'dtb-j700', 't8132-j713.dtb': b'dtb-j713'}

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = root = Path(temp.name)
        self.esp = root / 'esp'
        (self.esp / 'm1n1').mkdir(parents=True)
        self.boot = self.esp / 'm1n1/boot.bin'
        self.ctxr = self.esp / 'm1n1/boot-ctxr.bin'
        self.boot.write_bytes(FROZEN)
        os.utime(self.boot, (1000000, 1000000))
        self.dtbs = root / 'dtbs'
        self.dtbs.mkdir()
        for name, data in self.TREES.items():
            (self.dtbs / name).write_bytes(data)
        (root / 'm1n1.bin').write_bytes(AURA)
        (root / 'u-boot-nodtb.bin').write_bytes(UBOOT)
        run = root / 'run'
        run.mkdir()
        bindir = root / 'bin'
        bindir.mkdir()
        # The ESP mount becomes a link to the fixture ESP; umount removes it.
        (bindir / 'functions.sh').write_text(
            'info() { :; }\nwarn() { echo "$@" >&2; }\n'
            f'mount_sys_esp() {{ ln -s "{self.esp}" "$1"; }}\n')
        (bindir / 'umount').write_text('#!/bin/sh\nrm -f "$1"\n')
        (bindir / 'umount').chmod(0o755)
        text = SCRIPT.read_text()
        for system, fixture in (('/run/', f'{run}/'), ('/etc/sysconfig/', f'{root}/sysconfig-')):
            self.assertIn(system, text)
            text = text.replace(system, fixture)
        self.script = bindir / 'update-m1n1'
        self.script.write_text(text)
        self.script.chmod(0o755)
        self.compatible = root / 'compatible'
        self.marker = root / 'monitor-free'

    def run_update(self, *args, shell='sh', **env):
        environment = dict(os.environ, PATH=f'{self.root / "bin"}:{os.environ["PATH"]}', LC_ALL='C',
                           SOURCE=str(self.root), DTBS=f'{self.dtbs}/*.dtb',
                           CONFIG=str(self.root / 'm1n1.conf'),
                           AURORA_DEVICE_TREE_COMPATIBLE=str(self.compatible),
                           AURORA_MONITOR_FREE_MARKER=str(self.marker))
        environment.update(env)
        return subprocess.run([shell, str(self.script), *args], env=environment,
                              capture_output=True, text=True)

    def on(self, board, chip):
        self.compatible.write_bytes(compatible_file(board, chip))

    def monitor_free(self):
        self.marker.write_bytes(b'')

    def parts(self, trees, aura=AURA, options=b''):
        return aura + b''.join(self.TREES[name] for name in trees), UBOOT, options

    def read_parts(self, path):
        """A Stage 2 split at its gzip member: the aura and trees, U-Boot, the option lines."""
        data = path.read_bytes()
        cursor = data.index(b'\x1f\x8b\x08')
        inflater = zlib.decompressobj(wbits=31)
        return data[:cursor], inflater.decompress(data[cursor:]), inflater.unused_data

    def assert_frozen(self):
        self.assertEqual(self.boot.read_bytes(), FROZEN)
        self.assertEqual(self.boot.stat().st_mtime, 1000000)
        self.assertFalse((self.esp / 'm1n1/boot.bin.old').exists())
        self.assertFalse((self.esp / 'm1n1/boot.bin.new').exists())

    def assert_updated_boot_bin(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_parts(self.boot), self.parts(sorted(self.TREES)))
        self.assertEqual((self.esp / 'm1n1/boot.bin.old').read_bytes(), FROZEN)
        self.assertFalse(self.ctxr.exists())
        self.assertNotIn('WARNING', result.stderr)
        self.assertIn('m1n1/boot.bin', result.stdout)

    def test_macho_without_the_marker_keeps_updating_boot_bin(self):
        for chip in MACHO_CHIPS:
            with self.subTest(chip):
                self.boot.write_bytes(FROZEN)
                (self.esp / 'm1n1/boot.bin.old').unlink(missing_ok=True)
                self.on('j700', chip)
                self.assert_updated_boot_bin(self.run_update())

    def test_macho_with_the_marker_leaves_boot_bin_byte_identical(self):
        self.monitor_free()
        for chip in MACHO_CHIPS:
            with self.subTest(chip):
                self.on('j700', chip)
                self.ctxr.unlink(missing_ok=True)
                result = self.run_update()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_frozen()
                self.assertTrue(self.ctxr.is_file())

    def test_macho_with_the_marker_says_where_the_update_went_and_warns_nothing(self):
        self.monitor_free()
        self.on('j700', 't8140')
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertIn('m1n1 updated at', result.stdout)
        self.assertIn('boot-ctxr.bin', result.stdout)
        self.assert_frozen()

    def en_us(self):
        """An en_US.UTF-8 locale that sorts these trees unlike C, built here when the system has none."""
        environment = {'LC_ALL': 'en_US.UTF-8'}
        names = subprocess.run(['locale', '-a'], capture_output=True, text=True).stdout.split()
        if not any(name.lower().replace('-', '') == 'en_us.utf8' for name in names):
            path = self.root / 'locales'
            path.mkdir()
            try:
                subprocess.run(['localedef', '-i', 'en_US', '-f', 'UTF-8', str(path / 'en_US.UTF-8')],
                               capture_output=True)
            except OSError:
                pass
            if not (path / 'en_US.UTF-8').exists():
                self.skipTest('en_US.UTF-8 is not installed and localedef could not build it')
            environment['LOCPATH'] = str(path)
        order = subprocess.run(['bash', '-c', 'printf "%s\\n" t6040-j616s*.dtb'], cwd=self.dtbs,
                               env=dict(os.environ, **environment), capture_output=True, text=True).stdout
        if order.split() != ['t6040-j616s.dtb', 't6040-j616s-tether.dtb']:
            self.skipTest('this en_US.UTF-8 sorts the trees as C does, so it would prove nothing')
        return environment

    def test_macho_stage2_holds_only_this_boards_trees_in_byte_order(self):
        self.monitor_free()
        locale = self.en_us()
        # Arch's sh is bash, which sorts globs by locale.
        for shell in ('sh', 'bash'):
            with self.subTest(shell):
                self.on('j700', 't8140')
                self.assertEqual(self.run_update(shell=shell, **locale).returncode, 0)
                self.assertEqual(self.read_parts(self.ctxr),
                                 self.parts(['t8140-j700-ane-test.dtb', 't8140-j700.dtb']))
                self.on('j616s', 't6040')
                self.assertEqual(self.run_update(shell=shell, **locale).returncode, 0)
                self.assertEqual(self.read_parts(self.ctxr),
                                 self.parts(['t6040-j616s-tether.dtb', 't6040-j616s.dtb']))

    def test_macho_board_name_is_matched_whole(self):
        self.monitor_free()
        self.on('j616', 't6040')
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('no device tree for j616', result.stderr)
        self.assertFalse(self.ctxr.exists())

    def test_macho_update_keeps_the_previous_ctxr_stage2(self):
        self.monitor_free()
        self.on('j700', 't8140')
        self.assertEqual(self.run_update().returncode, 0)
        first = self.ctxr.read_bytes()
        self.assertFalse((self.esp / 'm1n1/boot-ctxr.bin.old').exists())
        (self.root / 'm1n1.bin').write_bytes(b'NEWER-AURA')
        self.assertEqual(self.run_update().returncode, 0)
        self.assertEqual((self.esp / 'm1n1/boot-ctxr.bin.old').read_bytes(), first)
        self.assertTrue(self.ctxr.read_bytes().startswith(b'NEWER-AURA'))
        self.assertFalse((self.esp / 'm1n1/boot-ctxr.bin.new').exists())
        self.assert_frozen()

    def test_macho_unchanged_stage2_keeps_the_rollback_copy(self):
        self.monitor_free()
        self.on('j700', 't8140')
        self.assertEqual(self.run_update().returncode, 0)
        old = self.esp / 'm1n1/boot-ctxr.bin.old'
        old.write_bytes(b'older generation')
        self.assertEqual(self.run_update().returncode, 0)
        self.assertEqual(old.read_bytes(), b'older generation')
        self.assert_frozen()

    def test_macho_explicit_boot_bin_target_is_redirected(self):
        self.monitor_free()
        self.on('j700', 't8140')
        self.assertEqual(self.run_update(str(self.boot)).returncode, 0)
        self.assert_frozen()
        self.assertTrue(self.ctxr.is_file())

    def test_macho_explicit_other_target_is_written_as_given(self):
        self.monitor_free()
        self.on('j700', 't8140')
        other = self.root / 'other.bin'
        result = self.run_update(str(other))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('WARNING', result.stderr)
        self.assertEqual(self.read_parts(other), self.parts(['t8140-j700-ane-test.dtb', 't8140-j700.dtb']))
        self.assert_frozen()
        self.assertFalse(self.ctxr.exists())

    def test_macho_without_a_tree_for_the_board_changes_nothing(self):
        # A warning, not a failure: kernel-install and the pacman hook run this.
        self.monitor_free()
        self.on('j873g', 't8152')
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('no device tree for j873g', result.stderr)
        self.assertIn('left as it is', result.stderr)
        self.assert_frozen()
        self.assertFalse(self.ctxr.exists())
        self.assertFalse((self.esp / 'm1n1/boot-ctxr.bin.new').exists())

    def test_a_ctxr_stage2_over_auras_slot_is_not_written(self):
        self.monitor_free()
        self.on('j700', 't8140')
        self.assertEqual(self.run_update().returncode, 0)
        first = self.ctxr.read_bytes()
        (self.root / 'm1n1.bin').write_bytes(b'\0' * (16 << 20))
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('16 MiB', result.stderr)
        self.assertEqual(self.ctxr.read_bytes(), first)
        self.assertFalse((self.esp / 'm1n1/boot-ctxr.bin.new').exists())
        self.assertFalse((self.esp / 'm1n1/boot-ctxr.bin.old').exists())
        self.assert_frozen()

    def test_earlier_chips_are_the_same_with_and_without_the_marker(self):
        for marked in (False, True):
            if marked:
                self.monitor_free()
            for chip in EARLIER_CHIPS:
                with self.subTest(chip=chip, marked=marked):
                    self.boot.write_bytes(FROZEN)
                    (self.esp / 'm1n1/boot.bin.old').unlink(missing_ok=True)
                    self.on('j274', chip)
                    self.assert_updated_boot_bin(self.run_update())

    def test_earlier_chip_leaves_a_present_ctxr_file_alone(self):
        self.monitor_free()
        self.on('j274', 't8103')
        self.ctxr.write_bytes(b'not ours')
        self.assertEqual(self.run_update().returncode, 0)
        self.assertEqual(self.ctxr.read_bytes(), b'not ours')

    def test_without_a_device_tree_it_writes_boot_bin_as_an_image_build_needs(self):
        self.monitor_free()
        self.assert_updated_boot_bin(self.run_update(str(self.boot)))

    def test_an_image_build_on_a_macho_host_ignores_its_device_tree(self):
        self.monitor_free()
        self.on('j700', 't8140')
        self.assert_updated_boot_bin(self.run_update(str(self.boot), AURORA_DEVICE_TREE_COMPATIBLE='/nonexistent'))

    def test_another_machine_is_treated_as_upstream_does(self):
        self.monitor_free()
        self.compatible.write_bytes(b'linux,dummy-virt\0')
        self.assert_updated_boot_bin(self.run_update())

    def test_fedoras_directory_form_selects_the_boards_trees(self):
        self.monitor_free()
        apple = self.root / 'dtb/apple'
        apple.mkdir(parents=True)
        for name, data in self.TREES.items():
            (apple / name).write_bytes(data)
        self.on('j700', 't8140')
        self.assertEqual(self.run_update(DTBS=str(self.root / 'dtb')).returncode, 0)
        self.assertEqual(self.read_parts(self.ctxr), self.parts(['t8140-j700-ane-test.dtb', 't8140-j700.dtb']))
        self.assert_frozen()

    def test_m1n1_conf_options_reach_the_ctxr_stage2(self):
        self.monitor_free()
        self.on('j700', 't8140')
        (self.root / 'm1n1.conf').write_text('chosen.bootargs=quiet\nnot an option\n')
        self.assertEqual(self.run_update().returncode, 0)
        self.assertEqual(self.read_parts(self.ctxr),
                         self.parts(['t8140-j700-ane-test.dtb', 't8140-j700.dtb'], options=b'chosen.bootargs=quiet\n'))


def board_image(board, chip):
    return AURA + device_tree([f'apple,{board}', f'apple,{chip}', 'apple,arm-platform']) + gzip.compress(UBOOT, mtime=0)


class PrepareCtxrStage2(unittest.TestCase):
    BOARDS = {'j274': 't8103', 'j700': 't8140', 'j616s': 't6040', 'j614s': 't6040', 'j713': 't8132', 'j873g': 't8152'}

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.m1n1 = Path(temp.name) / 'esp/m1n1'
        self.m1n1.mkdir(parents=True)
        (self.m1n1 / 'boot.bin').write_bytes(b'combined')
        for board, chip in self.BOARDS.items():
            (self.m1n1 / f'boot-{board}.bin').write_bytes(board_image(board, chip))

    def test_image_esp_carries_both_files_and_each_macho_boards_own(self):
        before = {path.name: path.read_bytes() for path in self.m1n1.iterdir()}
        written = prepare_ctxr.prepare(self.m1n1, self.m1n1)
        self.assertEqual(sorted(written), ['boot-ctxr-j614s.bin', 'boot-ctxr-j616s.bin', 'boot-ctxr-j700.bin',
                                           'boot-ctxr-j713.bin', 'boot-ctxr-j873g.bin', 'boot-ctxr.bin'])
        self.assertEqual((self.m1n1 / 'boot-ctxr.bin').read_bytes(), b'combined')
        self.assertEqual((self.m1n1 / 'boot-ctxr-j700.bin').read_bytes(), before['boot-j700.bin'])
        self.assertFalse((self.m1n1 / 'boot-ctxr-j274.bin').exists())
        for name, data in before.items():
            self.assertEqual((self.m1n1 / name).read_bytes(), data)

    def test_a_second_run_replaces_what_the_first_wrote(self):
        prepare_ctxr.prepare(self.m1n1, self.m1n1)
        (self.m1n1 / 'boot.bin').write_bytes(b'rebuilt combined')
        prepare_ctxr.prepare(self.m1n1, self.m1n1)
        self.assertEqual((self.m1n1 / 'boot-ctxr.bin').read_bytes(), b'rebuilt combined')

    def test_a_magic_inside_aura_is_not_mistaken_for_the_tree(self):
        path = self.m1n1 / 'boot-j700.bin'
        path.write_bytes(prepare_ctxr.DTB_MAGIC + b'\xff' * 60 + path.read_bytes())
        prepare_ctxr.prepare(self.m1n1, self.m1n1)
        self.assertTrue((self.m1n1 / 'boot-ctxr-j700.bin').is_file())

    def test_an_image_build_refuses_any_problem(self):
        cases = {
            'missing required board': lambda: (self.m1n1 / 'boot-j614s.bin').unlink(),
            'board file without its tree': lambda: (self.m1n1 / 'boot-j700.bin').write_bytes(b'no tree'),
            'oversized board file': lambda: (self.m1n1 / 'boot-j700.bin').write_bytes(
                board_image('j700', 't8140') + b'\0' * prepare_ctxr.MAX_STAGE2_BYTES),
            'oversized shared file': lambda: (self.m1n1 / 'boot.bin').write_bytes(
                b'\0' * (prepare_ctxr.MAX_STAGE2_BYTES + 1)),
        }
        for name, change in cases.items():
            with self.subTest(name):
                self.setUp()
                change()
                with self.assertRaises(ValueError):
                    prepare_ctxr.prepare(self.m1n1, self.m1n1)

    def test_a_shared_file_at_the_limit_is_accepted(self):
        (self.m1n1 / 'boot.bin').write_bytes(b'\0' * prepare_ctxr.MAX_STAGE2_BYTES)
        self.assertIn('boot-ctxr.bin', prepare_ctxr.prepare(self.m1n1, self.m1n1))

    def test_keep_going_only_leaves_out_the_file_with_the_problem(self):
        (self.m1n1 / 'boot-j614s.bin').unlink()
        (self.m1n1 / 'boot-j700.bin').write_bytes(board_image('j700', 't8140') + b'\0' * prepare_ctxr.MAX_STAGE2_BYTES)
        written = prepare_ctxr.prepare(self.m1n1, self.m1n1, keep_going=True)
        self.assertEqual(sorted(written), ['boot-ctxr-j616s.bin', 'boot-ctxr-j713.bin', 'boot-ctxr-j873g.bin', 'boot-ctxr.bin'])

    def test_chip_list_matches_the_update_tool(self):
        for chip in MACHO_CHIPS:
            self.assertTrue(prepare_ctxr.uses_macho([f'apple,{chip}']), chip)
        for chip in EARLIER_CHIPS:
            self.assertFalse(prepare_ctxr.uses_macho([f'apple,{chip}']), chip)


class Recipes(unittest.TestCase):
    def test_the_package_ships_the_tested_script_and_replaces_fedoras_files(self):
        spec = SPEC.read_text()
        self.assertRegex(spec, r'(?m)^Source0: update-m1n1$')
        self.assertIn('install -Dpm0755 %{SOURCE0} %{buildroot}%{_sbindir}/update-m1n1', spec)
        self.assertRegex(spec, r'(?m)^Name: update-m1n1$')
        self.assertIn('%config(noreplace) %{_sysconfdir}/sysconfig/update-m1n1', spec)
        self.assertIn('%{_kernel_install_dir}/15-update-m1n1.install', spec)
        self.assertIn('%transfiletriggerin -- /usr/lib/m1n1 /usr/lib64/m1n1 /usr/share/uboot/apple_m1 /etc/m1n1.conf', spec)

    def test_aura_needs_the_capability_only_this_package_provides(self):
        self.assertRegex(SPEC.read_text(), r'(?m)^Provides: aurora-stage2-ctxr-slot = 1$')
        self.assertRegex((ROOT / 'packages/aura/aura.spec').read_text(), r'(?m)^Requires: .*\baurora-stage2-ctxr-slot\b')

    def spec(self, package):
        return (ROOT / 'packages' / package / (package + '.spec')).read_text()

    def macro(self, package, name):
        return int(re.search(rf'(?m)^%global {name} ([01])$', self.spec(package))[1])

    def step(self, package, start, end):
        """The lines of a spec from the one starting `start` to the next one equal to `end`."""
        return re.search(rf'(?ms)^{re.escape(start)}.*?^{re.escape(end)}$', self.spec(package))[0]

    def test_an_aura_without_the_monitor_needs_a_kernel_that_keeps_its_code_in_the_window(self):
        # Both macros are checked against the pinned source and the resolved
        # configuration when the packages build, so this is what they ship.
        if self.macro('aura', 'monitor_free'):
            self.assertEqual(self.macro('kernel-aurora', 'ctxr_execmem'), 1,
                             'aura without the monitor needs CONFIG_ARM64_CTXR_EXECMEM=y')
        config = (ROOT / 'packages/kernel-aurora/config').read_text().splitlines()
        self.assertIn('CONFIG_ARM64_CTXR_EXECMEM=y', config)

    def test_the_macros_become_the_requirement_and_its_provider(self):
        self.assertIn('%if %{monitor_free}\nRequires: aurora-ctxr-execmem\n%endif\n', self.spec('aura'))
        kernel = self.spec('kernel-aurora')
        core = kernel.split('%package core', 1)[1].split('%package', 1)[0]
        self.assertIn('%if %{ctxr_execmem}\nProvides: aurora-ctxr-execmem\n%endif\n', core)
        self.assertIn('%if %{monitor_free}\ninstall -Dm644 /dev/null %{buildroot}%{_datadir}/aura/monitor-free\n%endif',
                      self.spec('aura'))

    def test_the_kernel_spec_refuses_a_macro_its_configuration_disagrees_with(self):
        check = self.step('kernel-aurora', 'ctxr=0', 'fi')
        for line, value, ok in (('CONFIG_ARM64_CTXR_EXECMEM=y', 1, True), ('', 0, True),
                                ('CONFIG_ARM64_CTXR_EXECMEM=y', 0, False), ('', 1, False)):
            with self.subTest(line=line, value=value), tempfile.TemporaryDirectory() as temporary:
                (Path(temporary) / '.config').write_text(line + '\n')
                result = subprocess.run(['sh', '-ec', check.replace('%{ctxr_execmem}', str(value))],
                                        cwd=temporary, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, ok, result.stderr)

    def test_the_aura_spec_refuses_a_macro_the_pinned_source_disagrees_with(self):
        check = self.step('aura', 'found=0', 'fi')
        cases = {'monitor': (('monitor.c',), 0), 'monitor-free': (('ctxr_exec.c',), 1),
                 'both': (('monitor.c', 'ctxr_exec.c'), 1), 'renamed': (('other.c',), 1)}
        for name, (files, source) in cases.items():
            for value in (0, 1):
                with self.subTest(name, value=value), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    (root / 'src').mkdir()
                    for file in files:
                        (root / 'src' / file).write_text('')
                    result = subprocess.run(['sh', '-ec', check.replace('%{monitor_free}', str(value))],
                                            cwd=root, capture_output=True, text=True)
                    self.assertEqual(result.returncode == 0, value == source, result.stderr)

    def test_the_package_keeps_the_upstream_license(self):
        spec = SPEC.read_text()
        self.assertRegex(spec, r'(?m)^Source3: LICENSE$')
        self.assertRegex(spec, r'(?m)^%license LICENSE$')
        self.assertIn('Copyright The Asahi Linux Contributors',
                      (ROOT / 'packages/update-m1n1/LICENSE').read_text())

    def test_the_tool_and_the_recipe_agree_on_the_marker_path(self):
        self.assertIn('/usr/share/aura/monitor-free', SCRIPT.read_text())

    def test_image_build_ignores_the_builders_device_tree(self):
        text = (ROOT / 'scripts/build-image').read_text()
        export = text.index('export AURORA_DEVICE_TREE_COMPATIBLE=/nonexistent')
        self.assertLess(export, text.index("subprocess.run(receipt['build_command']"))

    def test_image_build_adds_the_ctxr_files_after_the_finalizer(self):
        text = (ROOT / 'scripts/build-image').read_text()
        finalize = text.index('finalize-image"')
        ctxr = text.index('prepare-ctxr-stage2.py')
        archive = text.index('-filesystems.tar.zst')
        self.assertLess(finalize, ctxr)
        self.assertLess(ctxr, archive)

    def test_image_build_adds_the_ctxr_files_only_with_the_marker(self):
        text = (ROOT / 'scripts/build-image').read_text()
        mount = text.index('"$installer/root.img" "$basics_root"')
        guarded = text.index('if [[ -e $basics_root/usr/share/aura/monitor-free ]]; then\n'
                             '  python3 "$root/scripts/prepare-ctxr-stage2.py"')
        unmount = text.index('umount "$basics_root"')
        self.assertLess(mount, guarded)
        self.assertLess(guarded, unmount)
        self.assertEqual(text.count('prepare-ctxr-stage2.py'), 1)


if __name__ == '__main__':
    unittest.main()
