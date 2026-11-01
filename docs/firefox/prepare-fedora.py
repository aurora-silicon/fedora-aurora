#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply the opt-in browser delta to an exact, clean Fedora dist-git checkout."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("browser", choices=("firefox", "chromium"))
parser.add_argument("checkout", type=Path)
args = parser.parse_args()
pins = {
    "firefox": ("054f5ce6c099dfc8d788332920b4cb3397334ab6",
                "cd7e2ed4dbb2a5cbc947b2ad709f331b2b1bfd883b79f5ce14d26313cf8cd6aa",
                "0001-rdd-v4l2-request-proposal.patch",
                "0001-rdd-v4l2-request-proposal.patch"),
    "chromium": ("f202a8d8a1af53c6e462ee2034c947bd8c936e2f",
                 "37e8a6bb24e8a752d0aaef2d70ddb5fb527d9a3f039925d2bb3e9287b0e6b29b",
                 "0001-linux-stateless-decoder-broker-prototype.patch",
                 "chromium-linux-stateless-decoder-broker-prototype.patch"),
}
revision, spec_hash, patch_source, patch_dest = pins[args.browser]
checkout = args.checkout.resolve()
def git(*arguments):
    return subprocess.check_output(["git", "-C", str(checkout), *arguments], text=True).strip()
if git("rev-parse", "HEAD") != revision or git("status", "--porcelain"):
    parser.error("checkout must be clean at the pinned Fedora revision")
spec = checkout / (args.browser + ".spec")
if hashlib.sha256(spec.read_bytes()).hexdigest() != spec_hash:
    parser.error("Fedora spec bytes differ from the reviewed input")
directory = Path(__file__).resolve().parent.parent / args.browser
delta = str(directory / "fedora-45.spec.patch")
subprocess.run(["git", "-C", str(checkout), "apply", "--check", delta], check=True)
subprocess.run(["git", "-C", str(checkout), "apply", delta], check=True)
shutil.copyfile(directory / patch_source, checkout / patch_dest)
if args.browser == "firefox":
    shutil.copyfile(directory / "0002-opt-in-private-ffmpeg.patch",
                    checkout / "0002-opt-in-private-ffmpeg.patch")
print(f"Prepared {args.browser} at {revision}; build with --with avd_request")
