# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import unittest

from scoring import Frames, Gesture, SECOND


class RecordedK114s(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        decoder = Frames((0, 3023), (0, 1985))
        cls.frames = []
        for line in Path(__file__).with_name("k114s-evdev.txt").read_text().splitlines():
            if line.startswith("#"):
                continue
            stamp, kind, code, value = map(int, line.split())
            contacts = decoder.feed(kind, code, value)
            if contacts is not None:
                cls.frames.append((stamp, contacts))

    def replay(self, name, start, end):
        gesture = Gesture(name, start, (3024, 1986))
        for stamp, contacts in self.frames:
            if stamp > end:
                break
            gesture.frame(stamp, contacts)
        gesture.tick(end)
        return gesture

    def test_single_finger_holds(self):
        for start, end, passed in (
            (0, 4_000_000, True),               # 3.701 s
            (4_000_000, 7_800_000, True),       # 3.342 s
            (8_000_000, 11_200_000, False),     # 2.808 s
        ):
            with self.subTest(start=start):
                self.assertIs(bool(self.replay("hold", start, end).result), passed)

    def test_two_finger_hold(self):
        self.assertTrue(self.replay("hold-two", 31_500_000, 34_800_000).result)

    def test_three_finger_swipe(self):
        self.assertTrue(self.replay("swipe", 44_900_000, 45_700_000).result)

    def test_three_contacts_alone_do_not_pass(self):
        swipe = Gesture("swipe", 0, (3024, 1986))
        swipe.frame(0, {(0, 1): (.4, .5), (1, 2): (.5, .5), (2, 3): (.6, .5)})
        swipe.frame(100_000, {(0, 1): (.4, .2), (1, 2): (.5, .2), (2, 3): (.6, .5)})
        swipe.frame(200_000, {(0, 1): (.4, .2), (1, 2): (.5, .2), (2, 4): (.6, .2)})
        self.assertIsNone(swipe.result)

    def test_stationary_hold_and_contact_replacement(self):
        gesture = Gesture("hold", 0, (3024, 1986))
        gesture.frame(0, {(0, 1): (.5, .62)})
        gesture.frame(SECOND, {(0, 2): (.5, .62)})
        gesture.tick(3 * SECOND)
        self.assertIsNone(gesture.result)
        gesture.tick(4 * SECOND)
        self.assertTrue(gesture.result)

    def test_touch_from_previous_step_requires_release(self):
        gesture = Gesture("hold", 0, (3024, 1986), wait_for_release=True)
        gesture.frame(0, {(0, 1): (.5, .62)})
        gesture.tick(4 * SECOND)
        self.assertIsNone(gesture.result)
        gesture.frame(5 * SECOND, {})
        gesture.frame(6 * SECOND, {(0, 2): (.5, .62)})
        gesture.tick(9 * SECOND)
        self.assertTrue(gesture.result)


if __name__ == "__main__":
    unittest.main()
