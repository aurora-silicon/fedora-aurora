# SPDX-License-Identifier: MIT
import contextlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from asahi_firmware.core import FWFile, FWPackage
from aurora_wifi_firmware import Refused, tree_hashes
from refresh import manifest, refresh


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

    def extract(self, source, destination):
        with FWPackage(destination) as package:
            package.add_file("brcm/radio.bin", FWFile("brcm/radio.bin", b"old radio"))
            package.add_file("new.bin", FWFile("new.bin", b"new"))

    def test_preview_and_install_keep_every_existing_file(self):
        before, hashes = manifest(self.vendor), tree_hashes(self.vendor)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(refresh(self.esp, check=True, extract=self.extract), 1)
            self.assertEqual(tree_hashes(self.vendor), hashes)
            self.assertFalse(self.backup.exists())
            self.assertEqual(refresh(self.esp, backup_root=self.backup, extract=self.extract), 1)
            self.assertEqual(refresh(self.esp, backup_root=self.backup, extract=self.extract), 0)
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
            refresh(self.esp, backup_root=self.backup, extract=bad_extract)
        self.assertEqual(tree_hashes(self.vendor), hashes)
        self.assertFalse(self.backup.exists())


if __name__ == "__main__":
    unittest.main()
