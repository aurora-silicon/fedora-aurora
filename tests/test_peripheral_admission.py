import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/aurora-firmware"
MT7932_FIRMWARE = (
    'mediatek/mt7932/IZUBA_WIFI_MT7932_patch_mcu_1_2_hdr.bin', 'mediatek/mt7932/IZUBA_W7932_2.bin',
    'mediatek/mt7932/ppr.bin', 'mediatek/mt7932/oca2.bin', 'mediatek/mt7932/wcal.bin',
    'mediatek/mt7932/config-original.bin', 'mediatek/MT7932B0_OS_TypeB_0.1.44.0_241001003711.bin',
    'mediatek/MT7932B1_OS_TypeB_0.1.133.0_260128190103.bin',
    'mediatek/MT7932_PTB_IzubaA_0.1.0.0_20251021141303.ptx', 'mediatek/j700-mt7932-btcal.bin',
    'mediatek/j700-mt7932-bdaddr.bin', 'mediatek/mt7932/policy/world-XZ.bin',
)




NEO = 'apple,j700\0apple,t8140\0'
M2 = 'apple,j413\0apple,t8112\0'


def device_tree(root, compatible, radio='pci14e4,4433', als_calibration=None, trackpad=True,
                trackpad_firmware=None):
    """A device tree in the shape of the live one: the parts the admission reads."""
    dt = root / 'dt'
    dt.mkdir(parents=True, exist_ok=True)

    def node(path, compatible, **properties):
        directory = dt / path
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'compatible').write_bytes(compatible.encode())
        for name, value in properties.items():
            (directory / name.replace('_', '-')).write_bytes(value.encode())
        return directory

    (dt / 'compatible').write_bytes(compatible.encode())
    soc = compatible.split('\0')[1].removeprefix('apple,')
    node('soc', 'simple-bus\0')
    wifi = '/soc/pcie@1cb0000000/pci@0,0/wifi@0,0'
    node(wifi.lstrip('/'), radio + '\0')
    (dt / 'aliases').mkdir(exist_ok=True)
    (dt / 'aliases/wifi0').write_bytes(wifi.encode() + b'\0')
    node('soc/aop@310c00000', f'apple,{soc}-aop\0')
    als = {} if als_calibration is None else {'firmware_name': als_calibration + '\0'}
    node('soc/aop@310c00000/als', f'apple,{soc}-aop-als\0apple,aop-als\0', **als)
    if trackpad:
        hid = node('soc/fifo@314b14000/input@8000', 'apple,dockchannel-hid\0')
        (hid / 'multi-touch').mkdir()
        if trackpad_firmware is not None:
            (hid / 'multi-touch/firmware-name').write_bytes(trackpad_firmware.encode() + b'\0')
    return dt


class PeripheralAdmissionTests(unittest.TestCase):
    def admit(self, root, compatible, bluetooth=False, **tree):
        dt = root / 'dt'
        if not dt.exists():
            device_tree(root, compatible, **tree)
        modprobe = root / 'modprobe'
        modprobe.write_text('#!/bin/sh\nprintf "%s\\n" "$1" >> "$AURORA_TEST_CALLS"\n')
        modprobe.chmod(0o755)
        calls = root / 'module-calls'
        calls.unlink(missing_ok=True)
        env = dict(
            os.environ,
            AURORA_DT_ROOT=str(dt),
            AURORA_FIRMWARE_ROOT=str(root / 'firmware'),
            AURORA_MODPROBE=str(modprobe),
            AURORA_TEST_CALLS=str(calls),
            AURORA_ADMIT_BLUETOOTH='1' if bluetooth else '0',
        )
        script = PACKAGE / 'aurora-peripheral-firmware.sh'
        result = subprocess.run(['bash', str(script)], check=True, env=env, capture_output=True)
        return calls.read_text().splitlines(), result.stderr

    @staticmethod
    def firmware(root, *names):
        for name in names:
            path = root / 'firmware' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')

    def neo(self, root):
        device_tree(root, NEO, radio='pci14c3,7932', als_calibration='apple/j700-aop-als-cal.bin',
                    trackpad_firmware='apple/tpmtfw-j700.bin')

    def test_neo_keyboard_probe_follows_firmware_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.neo(root)
            self.firmware(root, 'apple/tpmtfw-j700.bin')
            calls, stderr = self.admit(root, NEO)
            self.assertEqual(calls, ['dockchannel-hid'])
            self.assertNotIn(b'trackpad firmware', stderr)
            self.assertIn(b'ALS calibration apple/j700-aop-als-cal.bin missing', stderr)

            (root / 'firmware/apple/tpmtfw-j700.bin').unlink()
            calls, stderr = self.admit(root, NEO)
            self.assertIn(b'trackpad firmware apple/tpmtfw-j700.bin missing', stderr)
            self.assertEqual(calls, ['dockchannel-hid'])

    def test_neo_admits_aop_and_radio_once_their_firmware_is_in_place(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.neo(root)
            self.firmware(root, 'apple/tpmtfw-j700.bin', 'apple/j700-aop-als-cal.bin', *MT7932_FIRMWARE)
            calls, stderr = self.admit(root, NEO)
            self.assertEqual(calls, ['dockchannel-hid', 'aop', 'mt7932-fullmac'], stderr)
            calls, stderr = self.admit(root, NEO, bluetooth=True)
            self.assertEqual(calls, ['dockchannel-hid', 'aop', 'mt7932-fullmac', 'mt7932_bt_pcie'], stderr)

            (root / 'firmware' / MT7932_FIRMWARE[0]).unlink()
            calls, stderr = self.admit(root, NEO)
            self.assertEqual(calls, ['dockchannel-hid', 'aop'])
            self.assertIn(b'required firmware is missing: ' + MT7932_FIRMWARE[0].encode(), stderr)

    def test_selection_follows_the_device_tree_not_the_board(self):
        # The same board name with a Broadcom radio and an ALS that names no
        # calibration file: aop loads and the MT7932 drivers stay out.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls, stderr = self.admit(root, NEO)
            self.assertEqual(calls, ['dockchannel-hid', 'aop'], stderr)
        # An MT7932 behind wifi0 on another board is admitted as on the Neo.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.firmware(root, 'apple/tpmtfw-j413.bin', *MT7932_FIRMWARE)
            calls, stderr = self.admit(root, M2, radio='pci14c3,7932', trackpad_firmware='apple/tpmtfw-j413.bin')
            self.assertEqual(calls, ['dockchannel-hid', 'aop', 'mt7932-fullmac'], stderr)

    def test_other_macs_keep_their_keyboard_driver(self):
        # M2 and later MacBooks use the same driver; desktops only load it.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.firmware(root, 'apple/tpmtfw-j413.bin')
            calls, stderr = self.admit(root, M2, trackpad_firmware='apple/tpmtfw-j413.bin')
            self.assertEqual(calls, ['dockchannel-hid', 'aop'])
            self.assertNotIn(b'trackpad firmware', stderr)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls, stderr = self.admit(root, M2, trackpad_firmware='apple/tpmtfw-j413.bin')
            self.assertEqual(calls, ['dockchannel-hid', 'aop'])
            self.assertIn(b'trackpad firmware apple/tpmtfw-j413.bin missing', stderr)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls, stderr = self.admit(root, 'apple,j274\0apple,t8103\0', trackpad=False)
            self.assertEqual(calls, ['dockchannel-hid', 'aop'])
            self.assertNotIn(b'trackpad firmware', stderr)

    def test_trackpad_firmware_is_the_one_its_node_names(self):
        # The multi-touch node's firmware-name decides the file, not the board.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.firmware(root, 'apple/tpmtfw-j700.bin')
            calls, stderr = self.admit(root, NEO, trackpad_firmware='apple/tpmtfw-j413.bin')
            self.assertEqual(calls, ['dockchannel-hid', 'aop'])
            self.assertIn(b'trackpad firmware apple/tpmtfw-j413.bin missing', stderr)
            self.assertNotIn(b'tpmtfw-j700', stderr)

            vendor = root / 'firmware/vendor/apple/tpmtfw-j413.bin'
            vendor.parent.mkdir(parents=True)
            vendor.write_bytes(b'fixture')
            calls, stderr = self.admit(root, NEO)
            self.assertNotIn(b'trackpad firmware', stderr)
        # Without the property the driver sends no firmware: nothing to check,
        # even with no trackpad file for the board.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls, stderr = self.admit(root, M2)
            self.assertEqual(calls, ['dockchannel-hid', 'aop'])
            self.assertNotIn(b'trackpad firmware', stderr)

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
