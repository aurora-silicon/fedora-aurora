# SPDX-License-Identifier: MIT
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from asahi_firmware.core import FWFile, FWPackage
from aurora_wifi_firmware import Refused, tree_hashes
from refresh import manifest, refresh

KVER = "6.18.4-400.aurora.fc44.aarch64"
FAKE_SECBOOT = """#!/bin/sh
d=$(dirname "$0")
case "$1" in
  status) cat "$d/status.json" ;;
  hook) echo "$*" >> "$d/hooks"; exit "$(cat "$d/hook-status")" ;;
  *) exit 2 ;;
esac
"""


def archive_pin(esp):
    return "sha256:" + hashlib.sha256((esp / "vendorfw" / "firmware.cpio").read_bytes()).hexdigest() + "\n"


def edit_tar(path, name, data):
    """Rewrite one member of a tar in place, as someone with the ESP could."""
    with tarfile.open(path) as archive:
        members = [(m, archive.extractfile(m).read() if m.isfile() else None) for m in archive.getmembers()]
    with tarfile.open(path, "w") as archive:
        for member, body in members:
            if member.name == name:
                body, member.size = data, len(data)
            archive.addfile(member, io.BytesIO(body) if body is not None else None)


class Case(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.esp = self.root / "esp"
        source = self.esp / "asahi"
        source.mkdir(parents=True)
        (source / "all_firmware.tar.gz").touch()
        self.vendor = self.esp / "vendorfw"
        self.vendor.mkdir()
        self.backup = self.root / "backup"
        with FWPackage(self.vendor) as package:
            package.add_file("brcm/radio.bin", FWFile("brcm/radio.bin", b"radio"))
            package.add_file("brcm/radio-alias.bin", FWFile("brcm/radio-alias.bin", b"radio"))
            package.add_file("apple/audio-tuning/unit.bin", FWFile("apple/audio-tuning/unit.bin", b"unit"),
                             mode=0o600)
        (self.vendor / "installer-extra").write_bytes(b"extra")
        # Never this host's aurora-secboot.
        self.cli = str(self.root / "no-aurora-secboot")

    def refresh(self, **options):
        options.setdefault("backup_root", self.backup)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = refresh(self.esp, extract=self.extract, cli=self.cli, **options)
        self.output = out.getvalue()
        return result

    def extract(self, source, destination):
        with FWPackage(destination) as package:
            package.add_file("brcm/radio.bin", FWFile("brcm/radio.bin", b"old radio"))
            package.add_file("new.bin", FWFile("new.bin", b"new"))


class RefreshTest(Case):
    def test_preview_and_install_keep_every_existing_file(self):
        before, hashes = manifest(self.vendor), tree_hashes(self.vendor)
        self.assertEqual(self.refresh(check=True), 1)
        self.assertEqual(tree_hashes(self.vendor), hashes)
        self.assertFalse(self.backup.exists())
        self.assertEqual(self.refresh(), 1)
        self.assertEqual(self.refresh(), 0)
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
            refresh(self.esp, backup_root=self.backup, extract=bad_extract, cli=self.cli)
        self.assertEqual(tree_hashes(self.vendor), hashes)
        self.assertFalse(self.backup.exists())


class SecureBootTest(Case):
    """A signed boot uses only the archive its UKI names, from aurora-secboot's pin."""

    def setUp(self):
        super().setUp()
        secboot = self.root / "secboot"
        self.keys = secboot / "keys"
        self.keys.mkdir(parents=True, mode=0o700)
        self.pin = self.keys / "vendorfw.sha256"
        self.old = archive_pin(self.esp)
        self.pin.write_text(self.old)
        cli = secboot / "aurora-secboot"
        cli.write_text(FAKE_SECBOOT)
        cli.chmod(0o755)
        self.cli, self.secboot = str(cli), secboot
        self.status()
        self.fail_hooks(False)

    def status(self, esp=None, present=True):
        (self.secboot / "status.json").write_text(json.dumps({
            "config_present": present, "key_dir": str(self.keys), "esp": str(esp or self.esp),
            "ukis": [{"kernel": KVER, "path": "a.efi"}, {"kernel": None, "path": "other.efi"}]}))

    def fail_hooks(self, fail):
        (self.secboot / "hook-status").write_text("1" if fail else "0")

    def hooks(self):
        log = self.secboot / "hooks"
        return log.read_text().splitlines() if log.exists() else []

    def refused(self):
        hashes = tree_hashes(self.vendor)
        with self.assertRaisesRegex(Refused, f"remove {self.pin} and run aurora-firmware-refresh again"):
            self.refresh()
        self.assertEqual(tree_hashes(self.vendor), hashes)
        self.assertFalse(self.backup.exists())
        self.assertEqual(self.hooks(), [])

    def test_a_pin_in_place_refuses_the_refresh_and_changes_nothing(self):
        # What a refresh adds comes from the ESP, which nothing can check; the
        # pin follows only verified files, so the owner must remove it.
        for pinned in [self.old, "none\n"]:
            with self.subTest(pin=pinned):
                self.pin.write_text(pinned)
                self.refused()
                self.assertEqual(self.pin.read_text(), pinned)

    def test_an_edited_esp_is_refused_too(self):
        edit_tar(self.vendor / "firmware.tar", "apple/audio-tuning/unit.bin", b"planted")
        self.refused()
        self.assertEqual(self.pin.read_text(), self.old)

    def test_a_preview_says_why_a_refresh_would_be_refused(self):
        hashes = tree_hashes(self.vendor)
        self.assertEqual(self.refresh(check=True), 1)
        self.assertIn(f"Secure boot: aurora-secboot's vendor firmware pin {self.pin} is in place", self.output)
        self.assertEqual(tree_hashes(self.vendor), hashes)
        self.assertEqual(self.pin.read_text(), self.old)

    def test_after_the_owner_removes_the_pin_the_ukis_are_rebuilt(self):
        # Removing the pin is the owner's explicit acceptance; aurora-secboot
        # then pins the new archive on the UKI build, not this tool.
        self.pin.unlink()
        self.assertEqual(self.refresh(), 1)
        self.assertNotEqual(archive_pin(self.esp), self.old)
        self.assertFalse(self.pin.exists())
        self.assertEqual(self.hooks(), [f"hook add {KVER}"])

    def test_failed_rebuild_names_the_command(self):
        self.pin.unlink()
        self.fail_hooks(True)
        with self.assertRaisesRegex(Refused, f"'aurora-secboot hook add {KVER}' succeeds"):
            self.refresh()

    def left_alone(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.refresh(), 1)
        self.assertEqual(self.pin.read_text(), self.old)
        self.assertEqual(self.hooks(), [])

    def test_unconfigured_secure_boot_is_left_alone(self):
        self.status(present=False)
        self.left_alone()

    def test_secure_boot_on_another_esp_is_left_alone(self):
        self.status(esp=self.root)
        self.left_alone()


if __name__ == "__main__":
    unittest.main()
