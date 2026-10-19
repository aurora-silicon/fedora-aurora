"""Exercise the shipped calibration cache and filesystem safety with raw fixtures."""
import hashlib
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import subprocess

from test_sep_calibration import synthetic_fsc2_image

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'packages/aurora-sep/prepare-sep-calibration'
EXTRACTOR = ROOT / 'packages/aurora-sep/extract-mesa-calibration'
helper = types.ModuleType('prepare_sep_calibration')
exec(compile(HELPER.read_text(), str(HELPER), 'exec'), helper.__dict__)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.device = self.root / 'readonly-isc'
        self.original = b'prefix' + synthetic_fsc2_image() + b'padding'
        self.device.write_bytes(self.original)
        self.device.chmod(0o400)
        self.state = self.root / 'state'
        self.firmware = self.root / 'firmware'

    def prepare(self, uuid='fixture-partuuid'):
        helper.prepare(self.device, uuid, self.state, self.firmware,
                       'apple/mesacal-j700.bin', EXTRACTOR)

    def test_extract_and_reuse_machine_bound_private_cache(self):
        self.prepare()
        output = self.firmware / 'apple/mesacal-j700.bin'
        self.assertEqual(output.read_bytes(), synthetic_fsc2_image())
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        with patch.object(helper.subprocess, 'run', side_effect=AssertionError('cache miss')):
            self.prepare()
        self.assertEqual(self.device.read_bytes(), self.original)

    def test_corrupt_cache_and_different_partition_are_reextracted(self):
        self.prepare()
        (self.state / 'mesa-calibration.bin').write_bytes(b'corrupt')
        real_run = subprocess.run
        with patch.object(helper.subprocess, 'run', wraps=real_run) as run:
            self.prepare()
            self.assertEqual(run.call_count, 1)
            self.prepare('different-partition')
            self.assertEqual(run.call_count, 2)
        self.assertEqual((self.state / 'mesa-calibration.bin').read_bytes(), synthetic_fsc2_image())

    def test_failed_refresh_does_not_replace_cached_or_live_firmware(self):
        self.prepare()
        before = (self.firmware / 'apple/mesacal-j700.bin').read_bytes()
        self.device.chmod(0o600)
        self.device.write_bytes(b'no calibration')
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare('replacement-isc')
        self.assertEqual((self.firmware / 'apple/mesacal-j700.bin').read_bytes(), before)
        self.assertEqual((self.state / 'mesa-calibration.bin').read_bytes(), before)

    def test_symlink_state_and_firmware_directory_rejected(self):
        target = self.root / 'target'
        target.mkdir()
        self.state.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.prepare()
        self.state.unlink()
        self.firmware.mkdir()
        (self.firmware / 'apple').symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(list(target.iterdir()), [])

    def test_dt_firmware_name_is_used_and_cannot_escape_firmware_directory(self):
        sensor = self.root / 'dt/spi/fingerprint@0'
        sensor.mkdir(parents=True)
        (sensor / 'compatible').write_bytes(b'apple,mesa-fingerprint\0')
        (sensor / 'firmware-name').write_bytes(b'apple/mesacal-j700.bin\0')
        self.assertEqual(helper.firmware_name(self.root / 'dt'), 'apple/mesacal-j700.bin')
        (sensor / 'firmware-name').write_bytes(b'apple/../../escape.bin\0')
        with self.assertRaises(ValueError):
            helper.firmware_name(self.root / 'dt')
