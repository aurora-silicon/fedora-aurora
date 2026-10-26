"""The shipped helper and extractor together, on raw synthetic containers."""
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

from test_sep_calibration import synthetic_fsc2_image, synthetic_record

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'packages/aurora-sep/prepare-sep-calibration'
EXTRACTOR = ROOT / 'packages/aurora-sep/extract-mesa-calibration'
helper = types.ModuleType('prepare_sep_calibration')
exec(compile(HELPER.read_text(), str(HELPER), 'exec'), helper.__dict__)
IDENTITY = (0x8132, 0x0011223344556677, b'TESTSERIAL1')


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.device = self.root / 'readonly-isc'
        self.state = self.root / 'state'
        self.run = self.root / 'run'
        self.firmware = self.root / 'firmware'
        self.target = self.firmware / 'apple/mesacal-j700.bin'

    def container(self, record):
        self.original = b'prefix' + record + b'padding'
        self.device.write_bytes(self.original)
        self.device.chmod(0o400)

    def prepare(self):
        data = self.device.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            ready = helper.prepare(lambda offset, length: data[offset:offset + length], self.device,
                                   self.state, self.run, self.firmware, 'apple/mesacal-j700.bin',
                                   EXTRACTOR, IDENTITY)
        self.output = out.getvalue()
        return ready

    def test_every_preparation_reads_the_container_again(self):
        self.container(synthetic_record())
        real_run = subprocess.run
        with patch.object(helper.subprocess, 'run', wraps=real_run) as run:
            self.assertTrue(self.prepare())
            self.assertTrue(self.prepare())
            self.assertEqual(run.call_count, 2)
        self.assertEqual(self.target.read_bytes(), synthetic_record())
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertFalse((self.state / 'mesa-calibration.bin').exists())
        self.assertEqual(self.device.read_bytes(), self.original)

    def test_a_standalone_image_without_factory_records_is_never_installed(self):
        self.container(synthetic_fsc2_image())
        self.assertFalse(self.prepare())
        self.assertFalse(self.target.exists())
        self.assertFalse((self.run / helper.READY).exists())
        self.assertIn('needs a calibration refresh', self.output)
        self.assertEqual(self.device.read_bytes(), self.original)

    def test_a_failed_extraction_leaves_live_firmware_and_no_readiness(self):
        self.container(synthetic_record())
        self.assertTrue(self.prepare())
        before = self.target.read_bytes()
        self.device.chmod(0o600)
        self.device.write_bytes(b'no calibration')
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare()
        self.assertEqual(self.target.read_bytes(), before)
        self.assertFalse((self.run / helper.READY).exists())

    def test_symlink_state_and_firmware_directory_rejected(self):
        self.container(synthetic_record())
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
