#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply the reviewed RDD delta to an exact, clean Fedora 44 dist-git tree."""

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess


REVISION = "1465e7dfc36e96ec3825c12f3dbed41c426e080d"
SPEC_SHA256 = "bc4c75cf7bfbd63781433fa28c97cb01f5433acf114b483015cd7abd56ebc807"

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("checkout", type=Path)
args = parser.parse_args()
checkout = args.checkout.resolve()


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), *arguments], text=True
    ).strip()


if git("rev-parse", "HEAD") != REVISION or git("status", "--porcelain"):
    parser.error("checkout must be clean at the pinned Fedora revision")
spec = checkout / "firefox.spec"
if hashlib.sha256(spec.read_bytes()).hexdigest() != SPEC_SHA256:
    parser.error("Fedora spec bytes differ from the reviewed input")

source_dir = Path(__file__).resolve().parent
delta = source_dir / "fedora-44-157.spec.patch"
subprocess.run(["git", "-C", str(checkout), "apply", "--check", str(delta)], check=True)
subprocess.run(["git", "-C", str(checkout), "apply", str(delta)], check=True)
shutil.copyfile(
    source_dir / "0001-rdd-v4l2-request.patch",
    checkout / "0001-rdd-v4l2-request.patch",
)
print("Prepared Firefox 157.0.1; build with --with avd_request")
