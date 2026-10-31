#!/usr/bin/env python3
"""Select RPMs affected by a push or PR; manual runs may request a set."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
names = sorted(p.parent.name for p in (root / "packages").glob("*/*.spec"))
event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
requested = event.get("inputs", {}).get("packages", "").split()
event_name = os.environ["GITHUB_EVENT_NAME"]
before = (event.get("pull_request", {}).get("base", {}).get("sha", "")
          if event_name == "pull_request" else event.get("before", ""))
if requested:
    if not set(requested) <= set(names):
        raise SystemExit("Unknown requested package")
    result = sorted(set(requested))
elif event_name not in ("push", "pull_request") or not before.strip("0"):
    result = names
else:
    paths = subprocess.check_output([
        "git", "diff", "--name-only", before, os.environ["GITHUB_SHA"],
    ], cwd=root, text=True).splitlines()
    if {"scripts/test-graphics-upgrade", "scripts/test-fex-overlay-upgrade"} & set(paths):
        paths.extend(f"packages/{name}/{name}.spec" for name in
                     ("mesa-aurora", "mesa-aurora-fex-guest", "aurora-flatpak-gl") if name in names)
    if {"scripts/build-avd-fedora", "scripts/check-avd-install.py", "docs/firefox/check-proposal.py"} & set(paths):
        paths.extend(f"packages/{name}/{name}.spec" for name in
                     ("ffmpeg-avd", "libva-v4l2-request") if name in names)
    if "sources.json" in paths:
        previous = json.loads(subprocess.check_output(
            ["git", "show", before + ":sources.json"], cwd=root, text=True))
        current = json.loads((root / "sources.json").read_text())
        changed = {key for key in previous.keys() | current.keys()
                   if previous.get(key) != current.get(key)}
        if changed <= set(names):
            paths.remove("sources.json")
            paths.extend(f"packages/{name}/{name}.spec" for name in sorted(changed))
    if {"sources.json", ".github/workflows/rpms.yml", "scripts/build-rpm", "scripts/build-receipt.py", "scripts/fetch-sources.py", "scripts/build-flatpak-gl-repo"} & set(paths):
        result = names
    else:
        result = sorted({p.split("/")[1] for p in paths
                         if p.startswith("packages/") and p.split("/")[1] in names})
# Recipes that ship x86 code (for FEX guests) declare an x86_64 builder.
x86 = {n for n in names
       if "# aurora-builder: x86_64" in (root / "packages" / n / (n + ".spec")).read_text().splitlines()}
print("packages=" + json.dumps([n for n in result if n not in x86]))
print("x86_packages=" + json.dumps([n for n in result if n in x86]))
