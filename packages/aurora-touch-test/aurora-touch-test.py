#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
import argparse
import fcntl
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import select
import struct
import subprocess
import tempfile
import threading
import time

from scoring import EV_SYN, Frames, Gesture, SECOND, SYN_DROPPED

# EVIOCSCLOCKID from linux/input.h on Fedora's supported architectures.
EVIOCSCLOCKID = 0x400445A0


def monotonic_us():
    return time.monotonic_ns() // 1000


class TouchInput:
    def __init__(self, path):
        from evdev import InputDevice, ecodes as e

        self.device = InputDevice(path)
        axes = dict(self.device.capabilities().get(e.EV_ABS, []))
        required = {e.ABS_MT_SLOT, e.ABS_MT_TRACKING_ID, e.ABS_MT_POSITION_X, e.ABS_MT_POSITION_Y}
        if e.INPUT_PROP_DIRECT not in self.device.input_props() or not required <= axes.keys():
            raise ValueError("Choose a direct touchscreen with type B multitouch slots.")
        ranges = [(axes[code].min, axes[code].max)
                  for code in (e.ABS_MT_POSITION_X, e.ABS_MT_POSITION_Y)]
        if any(low >= high for low, high in ranges):
            raise ValueError("The touchscreen reported invalid coordinate ranges.")
        fcntl.ioctl(self.device.fd, EVIOCSCLOCKID, struct.pack("i", time.CLOCK_MONOTONIC))
        self.frames = Frames(*ranges)
        self.frames.slot = axes[e.ABS_MT_SLOT].value
        self.btn_touch = e.BTN_TOUCH
        self.wait_for_release = self.btn_touch in self.device.active_keys()
        self.contacts = {}
        self.gesture = None
        self.step = None
        self.error = None
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.read)
        self.thread.start()

    def close(self):
        self.stop.set()
        self.thread.join()
        self.device.close()

    def arm(self, step, gesture, screen):
        with self.lock:
            self.step = step
            self.gesture = Gesture(gesture, monotonic_us(), screen,
                                   wait_for_release=self.wait_for_release or bool(self.contacts))
            return self.status(step)

    def status(self, step):
        if step != self.step:
            return {"ok": False, "note": "Touch test step changed"}
        ok, note = (False, self.error) if self.error else self.gesture.status()
        return {"ok": ok, "note": note}

    def read(self):
        dropped = False
        try:
            while not self.stop.is_set():
                ready, _, _ = select.select([self.device.fd], [], [], 0.05)
                with self.lock:
                    if not ready:
                        if self.gesture and not dropped:
                            self.gesture.tick(monotonic_us())
                        continue
                    try:
                        for event in self.device.read():
                            if event.type == EV_SYN and event.code == SYN_DROPPED:
                                dropped = True
                                self.error = "Touch events were lost. Restart the test."
                            if dropped:
                                continue
                            contacts = self.frames.feed(event.type, event.code, event.value)
                            if contacts is None:
                                continue
                            self.contacts = contacts
                            if self.wait_for_release:
                                self.wait_for_release = self.btn_touch in self.device.active_keys()
                                if self.wait_for_release:
                                    continue
                            if self.gesture:
                                self.gesture.frame(event.sec * SECOND + event.usec, contacts)
                    except BlockingIOError:
                        continue
        except OSError as exc:
            with self.lock:
                self.error = f"Touchscreen read failed ({exc.strerror})"


class Report:
    def __init__(self, path, mode):
        self.path = path
        self.mode = mode
        self.results = {}
        self.complete = False
        self.lock = threading.Lock()
        self.write()

    def write(self):
        rows = [self.results[step] for step in sorted(self.results)]
        passed = sum(row["ok"] for row in rows)
        overall = ("PASS" if passed == len(rows) else "FAIL") if self.complete else "INCOMPLETE"
        data = {
            "overall": overall, "mode": self.mode, "passed": passed,
            "failed": len(rows) - passed,
            "results": [{**row, "status": "PASS" if row["ok"] else "FAIL"} for row in rows],
        }
        pending = self.path.with_suffix(".tmp")
        pending.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        pending.replace(self.path)


def handler(touch, report, token, page):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_args):
            pass

        def reply(self, content, content_type="application/json"):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def localhost(self):
            if self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}":
                return True
            self.send_error(403)
            return False

        def authorized(self):
            if not self.localhost():
                return False
            if hmac.compare_digest(self.headers.get("X-Touch-Test", "").encode(), token.encode()):
                return True
            self.send_error(403)
            return False

        def do_GET(self):
            if self.path == "/":
                if self.localhost():
                    self.reply(page, "text/html; charset=utf-8")
                return
            if not self.authorized():
                return
            if self.path.startswith("/status/") and self.path[8:].isdigit():
                with touch.lock:
                    result = touch.status(int(self.path[8:]))
                self.reply(json.dumps(result).encode())
            else:
                self.send_error(404)

        def do_POST(self):
            if not self.authorized():
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 4096:
                    raise ValueError
                data = json.loads(self.rfile.read(length))
                if self.path == "/arm":
                    step, gesture, screen = data["step"], data["gesture"], data["screen"]
                    if (type(step) is not int or gesture not in ("hold", "hold-two", "swipe")
                            or len(screen) != 2 or not all(type(x) is int and x > 0 for x in screen)):
                        raise ValueError
                    response = touch.arm(step, gesture, screen)
                elif self.path == "/report":
                    step = data["step"]
                    row = {key: data[key] for key in ("name", "ok", "note", "source")}
                    if (type(step) is not int or type(row["ok"]) is not bool
                            or not all(isinstance(row[key], str) for key in ("name", "note", "source"))):
                        raise ValueError
                    with report.lock:
                        report.results[step] = row
                        report.write()
                    response = {}
                elif self.path == "/complete":
                    with report.lock:
                        expected = 3 if report.mode == "sleep" else 20
                        if set(report.results) != set(range(1, expected + 1)):
                            raise ValueError
                        report.complete = True
                        report.write()
                    response = {}
                else:
                    self.send_error(404)
                    return
            except (ValueError, KeyError, TypeError):
                self.send_error(400)
                return
            except OSError:
                self.send_error(500)
                return
            self.reply(json.dumps(response).encode())

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Run the full-screen touchscreen test in Firefox.")
    parser.add_argument("--device", required=True, help="readable touchscreen /dev/input/eventN")
    parser.add_argument("--output", type=Path, default=Path.cwd(), help="parent directory for the report")
    parser.add_argument("--sleep", action="store_true", help="run the short suspend and touch sequence")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("Run from the desktop session as an unprivileged user.")
    try:
        touch = TouchInput(args.device)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    try:
        args.output.mkdir(parents=True, exist_ok=True)
        run = Path(tempfile.mkdtemp(prefix="aurora-touch-test-", dir=args.output.absolute()))
        report = Report(run / "report.json", "sleep" if args.sleep else "full")
        print(f"Report {report.path}", flush=True)
        token = secrets.token_urlsafe()
        page = Path(__file__).resolve().with_name("index.html").read_bytes()
        with ThreadingHTTPServer(("127.0.0.1", 0), handler(touch, report, token, page)) as server:
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.start()
            try:
                with tempfile.TemporaryDirectory(prefix="firefox-", dir=run) as profile:
                    mode = "?sleep" if args.sleep else ""
                    url = f"http://127.0.0.1:{server.server_port}/{mode}#{token}"
                    return subprocess.call(["firefox", "--no-remote", "--profile", profile, "--kiosk", url])
            finally:
                server.shutdown()
                server_thread.join()
    finally:
        touch.close()


if __name__ == "__main__":
    raise SystemExit(main())
