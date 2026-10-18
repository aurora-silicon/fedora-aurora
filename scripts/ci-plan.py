#!/usr/bin/env python3
"""Select RPMs affected by a push; manual and pull-request runs check all."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
names = sorted(p.parent.name for p in (root / "packages").glob("*/*.spec"))
event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
requested = event.get("inputs", {}).get("packages", "").split()
if requested:
    if not set(requested) <= set(names):
        raise SystemExit("Unknown requested package")
    result = sorted(set(requested))
elif os.environ["GITHUB_EVENT_NAME"] != "push" or not event.get("before", "").strip("0"):
    result = names
else:
    paths = subprocess.check_output([
        "git", "diff", "--name-only", event["before"], os.environ["GITHUB_SHA"],
    ], cwd=root, text=True).splitlines()
    if {"sources.json", "scripts/build-rpm", "scripts/fetch-sources.py"} & set(paths):
        result = names
    else:
        result = sorted({p.split("/")[1] for p in paths
                         if p.startswith("packages/") and p.split("/")[1] in names})
print("packages=" + json.dumps(result))
