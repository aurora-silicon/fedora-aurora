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
    if "sources.json" in paths:
        previous = json.loads(subprocess.check_output(
            ["git", "show", before + ":sources.json"], cwd=root, text=True))
        current = json.loads((root / "sources.json").read_text())
        changed = {key for key in previous.keys() | current.keys()
                   if previous.get(key) != current.get(key)}
        if changed <= set(names):
            paths.remove("sources.json")
            paths.extend(f"packages/{name}/{name}.spec" for name in sorted(changed))
    if {"sources.json", ".github/workflows/rpms.yml", "scripts/build-rpm", "scripts/build-receipt.py", "scripts/fetch-sources.py", "scripts/build-flatpak-gl-repo", "scripts/fedoralib.py"} & set(paths):
        result = names
    else:
        result = sorted({p.split("/")[1] for p in paths
                         if p.startswith("packages/") and p.split("/")[1] in names})
# A pull request builds what it changed, plus every recipe that BuildRequires
# one of those packages' outputs; a push to main and a manual run without a
# list build the complete Fedora 45 set that publication needs ("full"), and a
# manual run with a list builds just that list for both releases.
if event_name == "pull_request" and set(result) != set(names):
    import re
    output = {}
    for name in names:
        text = (root / "packages" / name / (name + ".spec")).read_text()
        output[name] = name
        for m in re.finditer(r"^%package\s+(-n\s+)?(\S+)", text, re.M):
            output[m.group(2) if m.group(1) else name + "-" + m.group(2)] = name
    requires = {}
    for name in names:
        text = (root / "packages" / name / (name + ".spec")).read_text()
        for line in text.splitlines():
            if line.startswith("BuildRequires:"):
                for token in re.split(r"[\s,]+", line.split(":", 1)[1]):
                    owner = output.get(re.sub(r"\(.*", "", token))
                    if owner and owner != name:
                        requires.setdefault(owner, set()).add(name)
    selected = set(result)
    pending = list(selected)
    while pending:
        for dependent in requires.get(pending.pop(), ()):
            if dependent not in selected:
                selected.add(dependent)
                pending.append(dependent)
    result = sorted(selected)
full = (not requested and event_name != "pull_request") or set(result) == set(names)
print("full=" + ("true" if full else "false"))
# Recipes that ship x86 code (for FEX guests) declare an x86_64 builder.
x86 = {n for n in names
       if "# aurora-builder: x86_64" in (root / "packages" / n / (n + ".spec")).read_text().splitlines()}
print("packages=" + json.dumps([n for n in result if n not in x86]))
print("x86_packages=" + json.dumps([n for n in result if n in x86]))
