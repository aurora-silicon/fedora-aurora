#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Test-build variant of prepare-fedora.py: apply the same opt-in RDD delta to the
current head of a Fedora dist-git branch (no pinned revision or spec hash), by
anchored edits instead of a line-numbered spec patch. Hardware qualification only."""

import shutil
import sys
from pathlib import Path

checkout = Path(sys.argv[1]).resolve()
spec = checkout / "firefox.spec"
text = spec.read_text()


def once(old, new):
    global text
    if text.count(old) != 1:
        sys.exit(f"anchor not unique in firefox.spec: {old!r} ({text.count(old)})")
    text = text.replace(old, new)


text = "%bcond avd_request 0\n%if %{with avd_request}\n%global avd_release .avd1\n%endif\n\n" + text
once("Release:        1%{?dist}\n", "Release:        1%{?dist}%{?avd_release}\n")
once("Patch44:", "%if %{with avd_request}\nPatch900:       0001-rdd-v4l2-request.patch\n"
     "BuildRequires:  kernel-headers >= 6.5\n%endif\n\nPatch44:")
once("\nrm -f .mozconfig\n", "\n%if %{with avd_request}\n%patch -P900 -p1\n%endif\n\nrm -f .mozconfig\n")
spec.write_text(text)
shutil.copyfile(Path(__file__).resolve().parent / "0001-rdd-v4l2-request.patch",
                checkout / "0001-rdd-v4l2-request.patch")
print("Prepared", next(l for l in text.splitlines() if l.startswith("Version:")))
