#!/usr/bin/env python3
"""Build an immutable local F44 repository for the Neo Edge image."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

BASE = "https://github.com/aurora-silicon/fedora-aurora/releases/download/testing-20261116.1"
MANIFEST_SHA = "b064a50c585e7ccde76b123ff1988ccfa4c0349dd509dc20b2452c94420cc882"
SMOKED = {
    "kernel-aurora-core-7.3.0-42.fc44.aurora.aarch64.rpm": "794d0842c28cc3297695956da8d53247007ab28705f31631fd5d68a9f2030a5e",
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


def member_digest(rpm_path, member):
    with subprocess.Popen(["rpm2cpio", str(rpm_path)], stdout=subprocess.PIPE) as unpack:
        result = subprocess.run(["cpio", "--quiet", "-i", "--to-stdout", member],
                                stdin=unpack.stdout, stdout=subprocess.PIPE, check=True)
        unpack.stdout.close()
        if unpack.wait() or not result.stdout:
            raise ValueError(f"Missing RPM member {member}")
    return hashlib.sha256(result.stdout).hexdigest()


def read_signed(signed):
    eq = json.loads((signed / "equivalence.json").read_text())
    staged = rpm.inventory(signed / "rpms")
    if staged != eq["rpms"] or set(staged) != set(eq["unsigned_rpms"]):
        raise ValueError("Signing receipt differs from the artifact")
    result = []
    for name, row in staged.items():
        path = signed / "rpms" / name
        verify_signature(path)
        if row["main_header_and_payload_sha256"] != eq["unsigned_rpms"][name]["main_header_and_payload_sha256"]:
            raise ValueError("Signing changed RPM content")
        result.append((identity(path), path, row))
    return eq, result


def prepare(signed, replacement, out, receipt, replacement_signing_run):
    out.mkdir(parents=True)
    manifest_path = out.parent / "edge-baseline.json"
    fetch("manifest.json", manifest_path, 524288)
    manifest = manifest_path.read_bytes()
    if hashlib.sha256(manifest).hexdigest() != MANIFEST_SHA:
        raise ValueError("Baseline release manifest changed")
    base_rows = json.loads(manifest)["packages"]
    if sum(row["bytes"] for row in base_rows) > 2_000_000_000:
        raise ValueError("Baseline RPM size budget exceeded")
    subprocess.run(["rpmkeys", "--import", "keys/RPM-GPG-KEY-aurora"], check=True)
    eq, original = read_signed(signed)
    kernel_core = "kernel-aurora-core-7.3.0-42.fc44.aurora.aarch64.rpm"
    if eq["unsigned_rpms"][kernel_core]["sha256"] != SMOKED[kernel_core]:
        raise ValueError("Signing receipt names a different Neo-smoked kernel")
    _, new_mesa = read_signed(replacement)
    pin = "ef112c2b86e4e19b2317cd88918e673de7fd55cf"
    source = json.loads((replacement / "sources.json").read_text())
    if (source["kernel-aurora"]["commit"] != "6020f67d5ce13e7aae6820cd51ab70826404932c"
            or any(source[name]["commit"] != pin for name in ("mesa-aurora", "mesa-aurora-fex-guest"))):
        raise ValueError("Replacement receipt has the wrong frozen source pair")
    edge = {}
    paths = {}
    kernel = [row for row in original if row[0].startswith(("kernel-aurora", "aurora-userpages."))]
    for key, path, row in new_mesa:
        if not key.startswith(("aurora-flatpak-gl.", "mesa-aurora-")) or "-26.3.0-33.fc44.aurora." not in path.name:
            raise ValueError(f"Unexpected replacement Mesa package: {path.name}")
    for key, path, row in kernel + new_mesa:
        if key in edge:
            raise ValueError("Duplicate Edge package identity")
        edge[key] = {"filename": path.name, **row, "nevra": run("rpm", "-qp", "--qf", "%{NEVRA}", str(path))}
        paths[key] = path
    vulkan = paths["mesa-aurora-vulkan-drivers.aarch64"]
    runtime = {member: member_digest(vulkan, "./" + member) for member in (
        "usr/lib64/libvulkan_asahi.so", "usr/share/vulkan/icd.d/asahi_icd.aarch64.json")}
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
    for path in paths.values():
        shutil.copyfile(path, out / path.name)
    subprocess.run(["createrepo_c", "--checksum", "sha256", str(out)], check=True)
    receipt.write_text(json.dumps({"schema": 1, "fedora": 44, "baseline_sha256": MANIFEST_SHA,
                                  "signing_run": 44329906984, "replacement_signing_run": int(replacement_signing_run),
                                  "replacement_mesa": pin, "mesa_files": runtime, "signed_rpms": edge}, indent=2) + "\n")


if __name__ == "__main__":
    prepare(*(Path(arg) for arg in sys.argv[1:5]), sys.argv[5])
