import re
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "packages/aurora-remix-scripts/aurora-firstboot"


class FirstBootReloadTest(unittest.TestCase):
    def test_unit_changes_never_reload_pid1(self):
        # The swap and extras units run at the same time on first boot. Two
        # concurrent daemon reloads abort systemd 259 and freeze PID 1.
        code = "\n".join(line for line in SCRIPT.read_text().splitlines() if not line.lstrip().startswith("#"))
        calls = re.findall(r"systemctl\s+(?:enable|disable|mask|unmask|daemon-reload)[^\n]*", code)
        self.assertTrue(calls)
        for call in calls:
            self.assertIn("--no-reload", call, call)


if __name__ == "__main__":
    unittest.main()
