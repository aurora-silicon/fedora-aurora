#!/usr/bin/env python3
"""Record successful RPM outputs and the exact local recipe inputs."""
import hashlib
import json
import platform
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
name = sys.argv[1]
sys.path.insert(0, str(root / 'scripts'))
import fedoralib
fedora = fedoralib.release(os.environ.get('AURORA_FEDORA_RELEASE', '44'))
inputs = fedoralib.recipe_inputs(root, name, fedora)
outputs = []
for kind in ("RPMS", "SRPMS"):
    for path in sorted((root / "out/build" / name / kind).rglob("*.rpm")):
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        outputs.append({"filename": path.name, "sha256": digest, "bytes": path.stat().st_size})
if not outputs or not any(not row["filename"].endswith((".src.rpm", ".nosrc.rpm")) for row in outputs):
    raise SystemExit("A successful RPM build must produce binary and source artifacts")
destination = root / "out/manifests"
destination.mkdir(exist_ok=True)
(destination / (name + ".json")).write_text(json.dumps({
    "schema": 1, "package": name, "succeeded": True, "architecture": platform.machine(),
    "recipe_inputs": inputs, "artifacts": outputs,
    **({"fedora": fedora} if fedora != 44 else {}),
    "rpm": subprocess.check_output(["rpm", "--version"], text=True).strip(),
}, indent=2) + "\n")
