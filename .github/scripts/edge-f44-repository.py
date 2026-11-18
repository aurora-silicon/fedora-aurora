#!/usr/bin/env python3
"""Build an immutable local F44 repository for the Neo Edge image."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

BASE = "https://github.com/aurora-silicon/fedora-aurora/releases/download/testing-20261116.1"
MANIFEST_SHA = "b064a50c585e7ccde76b123ff1988ccfa4c0349dd509dc20b2452c94420cc882"
SMOKED = {
    "kernel-aurora-core-7.3.0-42.fc44.aurora.aarch64.rpm": "794d0842c28cc3297695956da8d53247007ab28705f31631fd5d68a9f2030a5e",
    "mesa-aurora-vulkan-drivers-26.3.0-32.fc44.aurora.aarch64.rpm": "470cb231e0a4d17434abe22033b5d6a4143834e830cb0a5031489cfd6b68ab89",
}
spec = importlib.util.spec_from_file_location("rpm_content", Path(__file__).with_name("edge-rpm-content.py"))
rpm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpm)


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def fetch(name, output, limit):
    subprocess.run(["curl", "-fsSL", "--retry", "3", "--max-time", "180",
                    "--max-filesize", str(limit), f"{BASE}/{name}", "-o", str(output)], check=True)


def identity(path):
    return run("rpm", "-qp", "--qf", "%{NAME}.%{ARCH}", str(path))


def verify_signature(path):
    if "digests signatures OK" not in run("rpmkeys", "--checksig", str(path)):
        raise ValueError(f"Missing Aurora signature: {path.name}")


def prepare(signed, out, receipt):
    out.mkdir(parents=True)
    manifest_path = out.parent / "edge-baseline.json"
    fetch("manifest.json", manifest_path, 524288)
    manifest = manifest_path.read_bytes()
    if hashlib.sha256(manifest).hexdigest() != MANIFEST_SHA:
        raise ValueError("Baseline release manifest changed")
    base_rows = json.loads(manifest)["packages"]
    if sum(row["bytes"] for row in base_rows) > 2_000_000_000:
        raise ValueError("Baseline RPM size budget exceeded")
    eq = json.loads((signed / "equivalence.json").read_text())
    staged = rpm.inventory(signed / "rpms")
    if staged != eq["rpms"] or set(staged) != set(eq["unsigned_rpms"]):
        raise ValueError("Signing receipt differs from the artifact")
    if any(eq["unsigned_rpms"][p]["sha256"] != digest for p, digest in SMOKED.items()):
        raise ValueError("Signing receipt names different Neo-smoked RPMs")
    subprocess.run(["rpmkeys", "--import", "keys/RPM-GPG-KEY-aurora"], check=True)
    edge = {}
    for name, row in staged.items():
        path = signed / "rpms" / name
        verify_signature(path)
        if row["main_header_and_payload_sha256"] != eq["unsigned_rpms"][name]["main_header_and_payload_sha256"]:
            raise ValueError("Signing changed RPM content")
        key = identity(path)
        if key in edge:
            raise ValueError("Duplicate Edge package identity")
        edge[key] = {"filename": name, **row, "nevra": run("rpm", "-qp", "--qf", "%{NEVRA}", str(path))}
    names = set()

    def add_base(row):
        name = row["filename"]
        path = out / name
        fetch(name, path, row["bytes"])
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if path.stat().st_size != row["bytes"] or digest != row["sha256"]:
            raise ValueError(f"Baseline digest changed: {name}")
        verify_signature(path)
        if identity(path) in edge:
            path.unlink()

    for row in base_rows:
        name = row["filename"]
        if not re.fullmatch(r"[A-Za-z0-9._+~-]+\.rpm", name) or name in names:
            raise ValueError("Invalid baseline RPM inventory")
        names.add(name)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(add_base, base_rows))
    for row in edge.values():
        source = signed / "rpms" / row["filename"]
        target = out / row["filename"]
        target.write_bytes(source.read_bytes())
    subprocess.run(["createrepo_c", "--checksum", "sha256", str(out)], check=True)
    receipt.write_text(json.dumps({"schema": 1, "fedora": 44, "baseline_sha256": MANIFEST_SHA,
                                  "signing_run": 44329906984, "signed_rpms": edge}, indent=2) + "\n")


if __name__ == "__main__":
    prepare(*(Path(arg) for arg in sys.argv[1:]))
