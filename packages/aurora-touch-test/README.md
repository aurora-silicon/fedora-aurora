# Aurora touch test

Install the optional `aurora-touch-test` RPM and run the test as the logged-in
desktop user. Use the event node for the touchscreen shown by `libinput list-devices`.

```sh
aurora-touch-test --device /dev/input/eventN --output "$PWD"
```

The command requires read access to that device. Where the desktop user lacks
access, a lab operator can grant it temporarily with
`sudo setfacl -m "u:$(id -un):r" /dev/input/eventN` and remove that ACL entry after
the test with `sudo setfacl -x "u:$(id -un)" /dev/input/eventN`. The app reads the
touchscreen without grabbing it, so the desktop can still handle gestures.
Use the internal display in its normal orientation and keep the test full-screen.

Firefox opens in kiosk mode with a disposable profile. Follow the instructions
and return to the kiosk after trying any gestures in the desktop. Use
`--sleep` for the short suspend and wake sequence.

The command prints the path to `report.json`. Each step is saved before the
next one begins. The overall status is PASS when all steps pass, FAIL when
the sequence finishes with any failed or skipped step, and INCOMPLETE if the
window closes early. Each row identifies its source as `evdev`, `browser`, or
`manual`. A raw three-finger swipe passes when each of the same three tracked
contacts moves up at least 20% of screen height. A timed hold requires the
same contacts to remain inside the target for the full interval. GNOME
overview and Files context-menu results reflect what the tester saw.

## Replay tests

Run `python3 -B -m unittest -v test_scoring` in the package source directory.
The fixture is a K114s evdev excerpt from the guided test. It retains just the
multitouch slot, tracking ID, position and frame events, with timestamps
relative to the excerpt start. The reported X and Y axis ranges are
0–3023 and 0–1985. The replay covers the observed 3.70 s, 3.34 s and 2.81 s
one-finger attempts, the two-finger hold and the three-finger swipe.
