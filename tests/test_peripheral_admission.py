import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/aurora-firmware"


class PeripheralAdmissionTests(unittest.TestCase):
    def admit(self, root, compatible):
        (root / "compatible").write_bytes(compatible)
        modprobe = root / "modprobe"
        modprobe.write_text('#!/bin/sh\nprintf "%s\\n" "$1" >> "$AURORA_TEST_CALLS"\n')
        modprobe.chmod(0o755)
        calls = root / "module-calls"
        calls.unlink(missing_ok=True)
        env = dict(
            os.environ,
            AURORA_DT_COMPATIBLE=str(root / "compatible"),
            AURORA_FIRMWARE_ROOT=str(root / "firmware"),
            AURORA_MODPROBE=str(modprobe),
            AURORA_TEST_CALLS=str(calls),
        )
        script = PACKAGE / "aurora-peripheral-firmware.sh"
        result = subprocess.run(["bash", str(script)], check=True, env=env, capture_output=True)
        return calls.read_text().splitlines(), result.stderr

    def test_neo_keyboard_probe_follows_firmware_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trackpad = root / "firmware/vendor/apple/tpmtfw-j700.bin"
            trackpad.parent.mkdir(parents=True)
            trackpad.write_bytes(b"fixture")
            calls, stderr = self.admit(root, b"apple,j700\0apple,t8140\0")
            self.assertEqual(calls, ["dockchannel-hid"])
            self.assertNotIn(b"trackpad firmware missing", stderr)

            trackpad.unlink()
            calls, stderr = self.admit(root, b"apple,j700\0apple,t8140\0")
            self.assertIn(b"trackpad firmware missing", stderr)
            self.assertEqual(calls, ["dockchannel-hid"])

    def test_other_macs_keep_their_keyboard_driver(self):
        # M2 and later MacBooks use the same driver; desktops only load it.
        with tempfile.TemporaryDirectory() as temporary:
            for compatible in [b"apple,j413\0apple,t8112\0", b"apple,j274\0apple,t8103\0"]:
                calls, stderr = self.admit(Path(temporary), compatible)
                self.assertEqual(calls, ["dockchannel-hid", "aop"])
                self.assertNotIn(b"trackpad firmware missing", stderr)

    def test_keyboard_driver_autoload_waits_for_admission(self):
        blacklist = (PACKAGE / "aurora-firmware-order.conf").read_text().splitlines()
        self.assertIn("blacklist dockchannel-hid", blacklist)
        setup = (PACKAGE / "module-setup.sh").read_text()
        self.assertRegex(setup, r"(?m)^installkernel\(\) \{ instmods .*\bdockchannel-hid\b")
        # Asahi unpacks the target Mac's firmware in its pre-udev 10 hook.
        self.assertIn("depends() { echo asahi-firmware; }", setup)
        self.assertIn('inst_hook pre-udev 20 "$moddir/admit-peripherals.sh"', setup)


# dracut's getarg, info and warn, as the hooks see them.
DRACUT_STUBS = r"""
getarg() {
    found=1
    for word in $AURORA_TEST_CMDLINE; do
        case $word in "$1"*) value=${word#"$1"}; found=0 ;; esac
    done
    [ "$found" = 0 ] && printf '%s\n' "$value"
    return "$found"
}
info() { echo "$@" >&2; }
warn() { echo "$@" >&2; }
"""


class VendorFirmwareHandoffTests(unittest.TestCase):
    """The initrd's pre-udev hooks, ending with Asahi's firmware loader."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "initrd"
        (self.root / "proc/device-tree/chosen").mkdir(parents=True)
        (self.root / "proc/device-tree/chosen/asahi,efi-system-partition").write_bytes(b"uuid\0")
        (self.root / "sys/bus/platform/drivers/nvme-apple/a.nvme/nvme/nvme0/nvme0n1").mkdir(parents=True)
        functions = self.root / "usr/share/asahi-scripts/functions.sh"
        functions.parent.mkdir(parents=True)
        # The ESP below stands in for the mounted one.
        functions.write_text('mount_sys_esp() { mkdir -p "$1"; }\n')
        self.bin = Path(directory.name) / "bin"
        self.bin.mkdir()
        for tool in ("modprobe", "umount", "sleep"):
            (self.bin / tool).write_text("#!/bin/sh\n")
            (self.bin / tool).chmod(0o755)
        self.esp = self.root / "run/.system-efi"
        self.archive = self.esp / "vendorfw/firmware.cpio"
        self.archive.parent.mkdir(parents=True)
        self.make_archive({"vendorfw/apple/tpmtfw-j700.bin": b"trackpad"})
        self.digest = "sha256:" + hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def make_archive(self, files):
        with tempfile.TemporaryDirectory() as temporary:
            names = []
            for name, data in files.items():
                path = Path(temporary) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                # Directories first, as in the installer's archive.
                parents = [str(parent) for parent in reversed(Path(name).parents) if str(parent) != "."]
                names += [parent for parent in parents if parent not in names] + [name]
            with self.archive.open("wb") as archive:
                subprocess.run(["cpio", "--quiet", "-o", "-H", "newc"], cwd=temporary, check=True,
                               input="\n".join(names).encode(), stdout=archive)

    def boot(self, cmdline):
        setup = (PACKAGE / "module-setup.sh").read_text()
        hooks = sorted((int(priority), name) for priority, name in
                       re.findall(r'inst_hook pre-udev (\d+) "\$moddir/([^"]+)"', setup))
        stderr = b""
        for priority, name in hooks:
            if priority >= 10:
                break
            env = dict(os.environ, AURORA_INITRD_ROOT=str(self.root), AURORA_TEST_CMDLINE=cmdline,
                       PATH=f"{self.bin}:{os.environ['PATH']}")
            # Hooks share dracut's shell, and its root variable.
            script = DRACUT_STUBS + 'root=block:/dev/root; . "$0"; [ "$root" = block:/dev/root ]'
            result = subprocess.run(["sh", "-c", script, str(PACKAGE / name)],
                                    check=True, env=env, capture_output=True)
            stderr += result.stderr
        # Asahi's pre-udev 10 loader: firmware already in /vendorfw was
        # loaded by the boot loader; otherwise unpack the ESP's archive.
        if not (self.root / "vendorfw").exists():
            with self.archive.open("rb") as archive:
                subprocess.run(["cpio", "--quiet", "-i"], cwd=self.root, check=True, stdin=archive)
        return stderr

    def firmware(self):
        vendorfw = self.root / "vendorfw"
        return sorted(str(path.relative_to(vendorfw)) for path in vendorfw.rglob("*") if path.is_file())

    def test_signed_boot_unpacks_the_archive_it_binds(self):
        (self.root / "vendorfw").mkdir()
        (self.root / "vendorfw/stale.bin").write_bytes(b"not from this boot")
        stderr = self.boot(f"quiet aurora.vendorfw={self.digest} lockdown=integrity")
        self.assertNotIn(b"<3>", stderr)
        self.assertEqual(self.firmware(), ["apple/tpmtfw-j700.bin"])
        self.assertEqual((self.root / "vendorfw/apple/tpmtfw-j700.bin").read_bytes(), b"trackpad")
        self.assertFalse((self.root / "run/.aurora-vendorfw.cpio").exists())

    def test_signed_boot_refuses_a_changed_archive(self):
        self.make_archive({"vendorfw/apple/tpmtfw-j700.bin": b"changed", "etc/initrd-release": b"changed"})
        stderr = self.boot(f"aurora.vendorfw={self.digest}")
        self.assertIn(b"<3>Aurora: the vendor firmware on the ESP does not match the digest", stderr)
        self.assertEqual(self.firmware(), [])
        self.assertFalse((self.root / "etc/initrd-release").exists())

    def test_signed_boot_without_a_trusted_archive_refuses_it(self):
        for value in ["none", "", self.digest.upper(), self.digest[:-1], "sha512:" + self.digest[7:]]:
            with self.subTest(value=value):
                (self.root / "vendorfw").mkdir(exist_ok=True)
                stderr = self.boot(f"aurora.vendorfw={value}")
                self.assertIn(b"<3>Aurora: this signed boot trusts no vendor firmware archive", stderr)
                self.assertEqual(self.firmware(), [])

    def test_unsigned_boot_keeps_the_asahi_loader(self):
        stderr = self.boot("quiet rhgb")
        self.assertEqual(stderr, b"")
        self.assertEqual(self.firmware(), ["apple/tpmtfw-j700.bin"])

    def test_hook_carries_its_tools(self):
        setup = (PACKAGE / "module-setup.sh").read_text()
        tools = re.search(r"inst_multiple (.*)", setup).group(1).split()
        for tool in ["cp", "rm", "mkdir", "cpio", "sha256sum", "seq", "sleep", "umount", "modprobe"]:
            self.assertIn(tool, tools)
        spec = (PACKAGE / "aurora-firmware.spec").read_text()
        self.assertIn("verify-vendor-firmware.sh", spec)


if __name__ == "__main__":
    unittest.main()
