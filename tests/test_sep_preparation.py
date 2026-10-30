"""Exercise the shipped calibration cache and filesystem safety with raw fixtures."""
import hashlib
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import subprocess

from test_sep_calibration import synthetic_fsc2_image, synthetic_record

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
        self.record = synthetic_record()
        self.source(self.record)
        self.state = self.root / 'state'
        self.firmware = self.root / 'firmware'

    def source(self, calibration):
        if self.device.exists():
            self.device.chmod(0o600)
        self.original = b'prefix' + calibration + b'padding'
        self.device.write_bytes(self.original)
        self.device.chmod(0o400)

    def prepare(self, uuid='fixture-partuuid'):
        helper.prepare(self.device, uuid, self.state, self.firmware,
                       'apple/mesacal-j700.bin', EXTRACTOR)

    def test_extract_and_reuse_machine_bound_private_cache(self):
        self.prepare()
        output = self.firmware / 'apple/mesacal-j700.bin'
        self.assertEqual(output.read_bytes(), self.record)
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
        self.assertEqual((self.state / 'mesa-calibration.bin').read_bytes(), self.record)

    def test_failed_refresh_does_not_replace_cached_or_live_firmware(self):
        self.prepare()
        before = (self.firmware / 'apple/mesacal-j700.bin').read_bytes()
        self.device.chmod(0o600)
        self.device.write_bytes(b'no calibration')
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare('replacement-isc')
        self.assertEqual((self.firmware / 'apple/mesacal-j700.bin').read_bytes(), before)
        self.assertEqual((self.state / 'mesa-calibration.bin').read_bytes(), before)

    def output(self):
        return self.firmware / 'apple/mesacal-j700.bin'

    def install_by_hand(self, data):
        self.output().parent.mkdir(parents=True)
        self.output().write_bytes(data)

    def test_standalone_fsc2_image_is_never_installed(self):
        # The J700 and J713 keep a bare FSC2 IMG4, which the enclave refuses
        # until it is resealed. The record the installer put there stays.
        self.source(synthetic_fsc2_image())
        sealed = b'installer sealed comb record'
        self.install_by_hand(sealed)
        self.prepare()
        self.assertEqual(self.output().read_bytes(), sealed)
        self.assertEqual((self.state / 'mesa-calibration.bin').read_bytes(),
                         synthetic_fsc2_image())
        # Nor is it installed where there is no file yet.
        self.output().unlink()
        self.prepare()
        self.assertFalse(self.output().exists())

    def test_a_file_this_helper_did_not_install_is_kept(self):
        foreign = b'a calibration the owner installed'
        self.install_by_hand(foreign)
        self.prepare()
        self.assertEqual(self.output().read_bytes(), foreign)
        self.assertFalse((self.state / 'installed.sha256').exists())

    def test_its_own_install_follows_a_changed_source(self):
        self.prepare()
        self.assertEqual(self.output().read_bytes(), self.record)
        newer = synthetic_record().replace(b'x' * 64, b'y' * 64)
        self.source(newer)
        self.prepare('updated-isc')
        self.assertEqual(self.output().read_bytes(), newer)
        recorded = (self.state / 'installed.sha256').read_text().strip()
        self.assertEqual(recorded, hashlib.sha256(newer).hexdigest())

    def test_an_install_from_a_release_without_the_record_counts_as_ours(self):
        # Releases up to 1-9 installed the cached bytes without recording
        # them; the cache is what they installed.
        self.prepare()
        (self.state / 'installed.sha256').unlink()
        newer = synthetic_record().replace(b'x' * 64, b'z' * 64)
        self.source(newer)
        self.prepare('updated-isc')
        self.assertEqual(self.output().read_bytes(), newer)

    def test_an_identical_file_is_not_rewritten(self):
        self.install_by_hand(self.record)
        before = self.output().stat().st_mtime_ns
        self.prepare()
        self.assertEqual(self.output().stat().st_mtime_ns, before)
        self.assertEqual((self.state / 'installed.sha256').read_text().strip(),
                         hashlib.sha256(self.record).hexdigest())

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

    def test_dt_firmware_name_list_picks_the_calibration(self):
        sensor = self.root / 'dt/spi@429108000/fingerprint@0'
        sensor.mkdir(parents=True)
        (sensor / 'compatible').write_bytes(b'apple,mesa-fingerprint\0')
        # The J616s node as the kernel exposes it.
        (sensor / 'firmware-name').write_bytes(
            b'apple/mesacal-j616s.bin\0apple/msrk-j616s.bin\0')
        self.assertEqual(helper.firmware_name(self.root / 'dt'), 'apple/mesacal-j616s.bin')
        (sensor / 'firmware-name').write_bytes(
            b'apple/msrk-j616s.bin\0apple/mesacal-j616s.bin\0')
        self.assertEqual(helper.firmware_name(self.root / 'dt'), 'apple/mesacal-j616s.bin')
        (sensor / 'firmware-name').write_bytes(b'apple/cal-j999.bin\0apple/other.bin\0')
        self.assertEqual(helper.firmware_name(self.root / 'dt'), 'apple/cal-j999.bin')
        for unsafe in (b'apple/mesacal-j616s.bin\0apple/../../escape.bin\0',
                       b'apple/mesacal-j616s.bin\0/etc/shadow\0', b'\0', b''):
            (sensor / 'firmware-name').write_bytes(unsafe)
            with self.assertRaises(ValueError):
                helper.firmware_name(self.root / 'dt')

    def test_dt_without_firmware_name_uses_the_default(self):
        sensor = self.root / 'dt/spi/fingerprint@0'
        sensor.mkdir(parents=True)
        (sensor / 'compatible').write_bytes(b'apple,mesa-fingerprint\0')
        self.assertEqual(helper.firmware_name(self.root / 'dt'), 'apple/mesa_calibration.bin')
