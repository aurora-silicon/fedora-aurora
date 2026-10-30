import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gl_payload', ROOT / 'packages/aurora-flatpak-gl/validate-repo.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
COMMIT = 'cf4e08105dfa526b8874318b6a52b3ce948f6297'


class PayloadValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write('.aurora-mesa-commit', COMMIT)
        elf = b'\x7fELF\x02\x01' + bytes(12) + struct.pack('<H', 183)
        for name in ('libvulkan_asahi.so', 'libvulkan_lvp.so', 'libEGL_mesa.so.0',
                     'libGLX_mesa.so.0', 'libLLVM.so.22.1'):
            self.write('lib/' + name, elf + f' Mesa (git-{COMMIT[:10]}), Borealis'.encode())
        for name in ('asahi', 'zink', 'swrast'):
            self.write('lib/dri/' + name + '_dri.so', elf)
        for path, lib in (('vulkan/icd.d/asahi_icd.aarch64.json', 'libvulkan_asahi.so'),
                          ('vulkan/icd.d/lvp_icd.aarch64.json', 'libvulkan_lvp.so'),
                          ('glvnd/egl_vendor.d/50_mesa.json', 'libEGL_mesa.so.0')):
            self.write(path, json.dumps({'ICD': {'library_path': '/usr/lib/aarch64-linux-gnu/GL/aurora/lib/' + lib}}))
        self.write('share/drirc.d/00-hk-defaults.conf', 'hk_report_honeykrisp_driver_id')

    def write(self, path, value):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.encode() if isinstance(value, str) else value)

    def test_complete_payload(self):
        validator.validate_payload(self.root, COMMIT)

    def test_missing_gl_library_is_rejected_despite_valid_stamp(self):
        (self.root / 'lib/libEGL_mesa.so.0').unlink()
        with self.assertRaises(FileNotFoundError):
            validator.validate_payload(self.root, COMMIT)

    def test_wrong_architecture_is_rejected(self):
        self.write('lib/dri/asahi_dri.so', b'\x7fELF\x02\x01' + bytes(12) + struct.pack('<H', 62))
        with self.assertRaisesRegex(ValueError, 'not an AArch64'):
            validator.validate_payload(self.root, COMMIT)

    def test_unstamped_driver_info_is_rejected(self):
        path = self.root / 'lib/libvulkan_asahi.so'
        path.write_bytes(path.read_bytes()[:20] + b'Mesa 26.3.0-devel, Borealis')
        with self.assertRaisesRegex(ValueError, 'driverInfo'):
            validator.validate_payload(self.root, COMMIT)

    def test_symlink_outside_payload_is_rejected(self):
        path = self.root / 'lib/dri/asahi_dri.so'
        path.unlink()
        path.symlink_to('/bin/sh')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            validator.validate_payload(self.root, COMMIT)

    def test_absent_json_target_is_rejected(self):
        self.write('glvnd/egl_vendor.d/50_mesa.json', json.dumps({'ICD': {'library_path': 'missing.so'}}))
        with self.assertRaisesRegex(ValueError, 'library_path'):
            validator.validate_payload(self.root, COMMIT)
