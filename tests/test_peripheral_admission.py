import os
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
