# SPDX-License-Identifier: GPL-2.0-only
"""Score Linux type B multitouch frames after SYN_REPORT."""
import math

EV_SYN, EV_ABS = 0, 3
SYN_REPORT, SYN_DROPPED = 0, 3
ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID = 47, 53, 54, 57
SECOND = 1_000_000


class Frames:
    def __init__(self, x_range, y_range):
        self.slot = 0
        self.slots = {}
        self.x_range = x_range
        self.y_range = y_range

    def feed(self, kind, code, value):
        if kind == EV_ABS:
            if code == ABS_MT_SLOT:
                self.slot = value
            elif code in (ABS_MT_TRACKING_ID, ABS_MT_POSITION_X, ABS_MT_POSITION_Y):
                # Axis values persist when a slot is reused. Drivers can omit
                # positions that equal the slot's last reported coordinates.
                self.slots.setdefault(self.slot, {})[code] = value
        if kind != EV_SYN or code != SYN_REPORT:
            return None
        contacts = {}
        for slot, values in self.slots.items():
            tracking = values.get(ABS_MT_TRACKING_ID, -1)
            if tracking >= 0:
                x0, x1 = self.x_range
                y0, y1 = self.y_range
                x = values.get(ABS_MT_POSITION_X)
                y = values.get(ABS_MT_POSITION_Y)
                contacts[slot, tracking] = (
                    None if x is None or y is None else
                    ((x - x0) / (x1 - x0), (y - y0) / (y1 - y0))
                )
        return contacts


class Gesture:
    def __init__(self, name, armed_at, screen, *, wait_for_release=False):
        self.name = name
        self.fingers = {"hold": 1, "hold-two": 2, "swipe": 3}[name]
        self.duration = {"hold": 3, "hold-two": 2, "swipe": 0}[name] * SECOND
        self.armed_at = armed_at
        self.width, self.height = screen
        self.wait_for_release = wait_for_release
        self.origins = {}
        self.since = None
        self.best = 0
        self.seen = 0
        self.result = None

    def frame(self, now, contacts):
        if self.result or now < self.armed_at:
            return
        if self.wait_for_release:
            self.wait_for_release = bool(contacts)
            return
        self.seen = max(self.seen, len(contacts))
        valid = len(contacts) == self.fingers and all(p is not None for p in contacts.values())
        if self.name != "swipe":
            # Same center and acceptance radius as the circle in index.html.
            radius = 0.16 * 1.35 * min(self.width, self.height)
            valid = valid and all(
                math.hypot((x - 0.5) * self.width, (y - 0.62) * self.height) <= radius
                for x, y in contacts.values()
            )
            self.tick(now)
        if not valid:
            self.since = None
            self.origins = {}
            return
        if self.since is None or self.origins.keys() != contacts.keys():
            self.since = now
            self.origins = contacts.copy()
        if self.name == "swipe":
            # Require all three original contacts to travel up. Lifts,
            # replacements and stationary extra fingers cannot move the score.
            travel = min(self.origins[key][1] - point[1] for key, point in contacts.items())
            self.best = max(self.best, travel)
            if travel >= 0.20:
                self.result = (True, f"All three fingers moved up at least {travel:.0%} of screen height")

    def tick(self, now):
        if self.result or self.since is None or self.name == "swipe":
            return
        elapsed = now - self.since
        self.best = max(self.best, elapsed)
        if elapsed >= self.duration:
            self.result = (True, f"Held for {elapsed / SECOND:.2f} s")

    def status(self):
        if self.result:
            return self.result
        if self.name == "swipe":
            return None, f"Saw up to {self.seen} fingers, all three moved up {self.best:.0%}"
        return None, f"Longest hold {self.best / SECOND:.2f} s"
