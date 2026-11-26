# SPDX-License-Identifier: MIT
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

from asahi_firmware.core import FWFile, FWPackage
from aurora_wifi_firmware import Refused, tree_hashes
from refresh import manifest, rebind_secure_boot, refresh


class RefreshTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.esp = Path(directory.name)
        source = self.esp / "asahi"
        source.mkdir()
        (source / "all_firmware.tar.gz").touch()
        self.vendor = self.esp / "vendorfw"
        self.vendor.mkdir()
        self.backup = self.esp / "backup"
        with FWPackage(self.vendor) as package:
            package.add_file("brcm/radio.bin", FWFile("brcm/radio.bin", b"radio"))
            package.add_file("brcm/radio-alias.bin", FWFile("brcm/radio-alias.bin", b"radio"))
            package.add_file("apple/audio-tuning/unit.bin", FWFile("apple/audio-tuning/unit.bin", b"unit"),
                             mode=0o600)
        (self.vendor / "installer-extra").write_bytes(b"extra")
        self.rebound = []

    def refresh(self, **options):
        return refresh(self.esp, extract=self.extract, secure_boot=self.rebound.append, **options)

    def extract(self, source, destination):
        with FWPackage(destination) as package:
            package.add_file("brcm/radio.bin", FWFile("brcm/radio.bin", b"old radio"))
            package.add_file("new.bin", FWFile("new.bin", b"new"))

    def test_preview_and_install_keep_every_existing_file(self):
        before, hashes = manifest(self.vendor), tree_hashes(self.vendor)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.refresh(check=True), 1)
            self.assertEqual(tree_hashes(self.vendor), hashes)
            self.assertFalse(self.backup.exists())
            self.assertEqual(self.rebound, [])
            self.assertEqual(self.refresh(backup_root=self.backup), 1)
            # Signed boots must name the new archive.
            self.assertEqual(self.rebound, [self.vendor / "firmware.cpio"])
            self.assertEqual(self.refresh(backup_root=self.backup), 0)
            self.assertEqual(len(self.rebound), 1)
        self.assertEqual({name: manifest(self.vendor)[name] for name in before}, before)
        self.assertEqual((self.vendor / "installer-extra").read_bytes(), b"extra")
        with tarfile.open(self.vendor / "firmware.tar") as archive:
            self.assertEqual(archive.getmember("apple/audio-tuning/unit.bin").mode, 0o600)
        backups = list(self.backup.glob("*/vendorfw"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(tree_hashes(backups[0]), hashes)

    def test_bad_candidate_leaves_live_files_unchanged(self):
        hashes = tree_hashes(self.vendor)

        def bad_extract(source, destination):
            self.extract(source, destination)
            (destination / "manifest.txt").write_text("FILE new.bin SHA256 " + "0" * 64 + "\n")

        with self.assertRaises(Refused):
            refresh(self.esp, backup_root=self.backup, extract=bad_extract, secure_boot=self.rebound.append)
        self.assertEqual(tree_hashes(self.vendor), hashes)
        self.assertFalse(self.backup.exists())
        self.assertEqual(self.rebound, [])


class SecureBootTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.cli = root / "aurora-secboot"
        self.cli.write_text("#!/bin/sh\nexit 1\n")
        self.cli.chmod(0o755)
        self.archive = root / "firmware.cpio"
        self.archive.write_bytes(b"new archive")
        self.keys = root / "keys"
        self.keys.mkdir(mode=0o700)
        self.pin = self.keys / "vendorfw.sha256"
        self.pin.write_text("sha256:" + "0" * 64 + "\n")
        self.status = {"config_present": True, "key_dir": str(self.keys),
                       "ukis": [{"kernel": "6.18.4-400.aurora.fc44.aarch64", "path": "a.efi"},
                                {"kernel": None, "path": "other.efi"}]}
        self.hook_status = 0
        self.calls = []

    def run_secboot(self, argv, **options):
        self.assertEqual(argv[0], str(self.cli))
        self.calls.append(argv[1:])
        if argv[1:] == ["status", "--json"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.status), "")
        return subprocess.CompletedProcess(argv, self.hook_status)

    def rebind(self):
        with contextlib.redirect_stdout(io.StringIO()):
            rebind_secure_boot(self.archive, cli=str(self.cli), run=self.run_secboot)

    def test_new_archive_is_pinned_and_every_uki_rebuilt(self):
        self.rebind()
        self.assertEqual(self.pin.read_text(), f"sha256:{hashlib.sha256(b'new archive').hexdigest()}\n")
        self.assertEqual(self.pin.stat().st_mode & 0o777, 0o600)
        self.assertEqual(sorted(path.name for path in self.keys.iterdir()), ["vendorfw.sha256"])
        self.assertEqual(self.calls, [["status", "--json"], ["hook", "add", "6.18.4-400.aurora.fc44.aarch64"]])

    def test_failed_rebuild_is_reported(self):
        self.hook_status = 1
        with self.assertRaisesRegex(Refused, "aurora-secboot hook add 6.18.4-400"):
            self.rebind()
        self.assertIn(hashlib.sha256(b"new archive").hexdigest(), self.pin.read_text())

    def test_unconfigured_secure_boot_is_left_alone(self):
        self.status["config_present"] = False
        old = self.pin.read_text()
        self.rebind()
        self.assertEqual(self.pin.read_text(), old)
        self.assertEqual(self.calls, [["status", "--json"]])
        self.cli.unlink()
        self.rebind()
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
