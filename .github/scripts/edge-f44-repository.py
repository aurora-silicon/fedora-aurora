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

BASE = "https://github.com/aurora-silicon/fedora-aurora/releases/download/testing-20261117.1"
MANIFEST_SHA = "d4c3690bb4c94e4ba746b32e76235fdd1354c497e77f41a3b59d289c96d5711c"
KERNEL = "e0ee46a18e33f859f6ad6863757a4650ff687ab6"
MESA = "418bf795a98c0cfe044f87d724a5db7b6b980b56"
KERNEL_VR = "-7.3.0-43.fc44.aurora."
MESA_VR = "-26.3.0-34.fc44.aurora."
# The unsigned CI RPMs smoked on the Neo before signing.
SMOKED = {
    "kernel-aurora-core-7.3.0-43.fc44.aurora.aarch64.rpm": "40816f71beeae7126fe339637fd97980ae52ac962151e110899b2befac9e4a84",
    "mesa-aurora-vulkan-drivers-26.3.0-34.fc44.aurora.aarch64.rpm": "7905f9656d28edac24366a97da6acf65994b99833eea098d738281872c4333e4",
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


def prepare(signed, sources, out, receipt, signing_run):
    signing_run = int(signing_run)
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
    source = json.loads(sources.read_text())
    if (source["kernel-aurora"]["commit"] != KERNEL
            or any(source[name]["commit"] != MESA for name in ("mesa-aurora", "mesa-aurora-fex-guest"))):
        raise ValueError("Signed RPMs were packaged from a different source pair")
    eq, packages = read_signed(signed)
    for name, digest in SMOKED.items():
        if eq["unsigned_rpms"].get(name, {}).get("sha256") != digest:
            raise ValueError(f"Signing receipt names a different Neo-smoked RPM: {name}")
    edge = {}
    paths = {}
    for key, path, row in packages:
        if key.startswith(("kernel-aurora", "aurora-userpages.")):
            version = KERNEL_VR
        elif key.startswith(("aurora-flatpak-gl.", "mesa-aurora-")):
            version = MESA_VR
        else:
            raise ValueError(f"Unexpected signed Edge package: {path.name}")
        if version not in path.name:
            raise ValueError(f"Signed Edge package has a stale version: {path.name}")
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
    # One signer run signed the kernel and Mesa; the replacement fields keep the proof schema.
    receipt.write_text(json.dumps({"schema": 1, "fedora": 44, "baseline_sha256": MANIFEST_SHA,
                                  "signing_run": signing_run, "replacement_signing_run": signing_run,
                                  "replacement_mesa": MESA, "mesa_files": runtime, "signed_rpms": edge}, indent=2) + "\n")


if __name__ == "__main__":
    prepare(*(Path(arg) for arg in sys.argv[1:5]), sys.argv[5])
