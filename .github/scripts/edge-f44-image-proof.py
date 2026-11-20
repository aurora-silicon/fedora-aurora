#!/usr/bin/env python3
"""Check the assembled Neo image against the verified F44 RPM inventory."""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

KREL = "7.3.0-43.fc44.aurora.aarch64"
KERNEL_DIGEST = "701ed7f29d693e439083508546d96c4917431e35f725465a154c855008c2c5bf"
SIGNING_RUN = 44694386531
MESA = "418bf795a98c0cfe044f87d724a5db7b6b980b56"
FILES = {
    f"root:usr/lib/modules/{KREL}/vmlinuz": KERNEL_DIGEST,
    f"boot:vmlinuz-{KREL}": KERNEL_DIGEST,
}
REQUIRED = {"kernel-aurora-core.aarch64", "kernel-aurora-modules-extra.aarch64",
            "mesa-aurora-vulkan-drivers.aarch64", "mesa-aurora-dri-drivers.aarch64"}


def proof(root, boot, input_receipt):
    roots = {"root": root.resolve(strict=True), "boot": boot.resolve(strict=True)}
    if (input_receipt["replacement_mesa"] != MESA
            or input_receipt["replacement_signing_run"] != SIGNING_RUN):
        raise ValueError("Expected the single kernel and Mesa signing receipt")
    mesa_files = input_receipt["mesa_files"]
    if set(mesa_files) != {"usr/lib64/libvulkan_asahi.so", "usr/share/vulkan/icd.d/asahi_icd.aarch64.json"}:
        raise ValueError("Replacement Mesa file inventory is incomplete")
    if any(not re.fullmatch(r"[a-f0-9]{64}", digest) for digest in mesa_files.values()):
        raise ValueError("Replacement Mesa file digests are invalid")
    exact = {**FILES, **{"root:" + name: digest for name, digest in mesa_files.items()}}
    for name, expected in exact.items():
        where, relative = name.split(":", 1)
        path = (roots[where] / relative).resolve(strict=True)
        if not path.is_relative_to(roots[where]):
            raise ValueError(f"Image member escapes its filesystem: {name}")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise ValueError(f"Image member differs from the candidate RPM bytes: {name}")
    signed = input_receipt["signed_rpms"]
    if input_receipt["signing_run"] != SIGNING_RUN or not REQUIRED <= signed.keys():
        raise ValueError("Image RPM input does not cover the tested package set")
    for key in ("mesa-aurora-vulkan-drivers.aarch64", "mesa-aurora-dri-drivers.aarch64"):
        if "-26.3.0-34.fc44.aurora.aarch64.rpm" not in signed[key]["filename"]:
            raise ValueError(f"Image candidate contains stale Mesa: {key}")
    installed = subprocess.check_output(
        ["rpm", "--root", str(root), "-qa", "--qf", "%{NAME}.%{ARCH}\t%{NEVRA}\n"], text=True)
    selected = []
    for line in installed.splitlines():
        key, nevra = line.split("\t", 1)
        if key in signed:
            if nevra != signed[key]["nevra"]:
                raise ValueError(f"Image selected a stale package: {key}")
            selected.append(key)
    if not REQUIRED <= set(selected):
        raise ValueError("Image is missing Edge runtime packages")
    repos = root / "etc/yum.repos.d/aurora.repo"
    if "enabled=0" not in repos.read_text().splitlines():
        raise ValueError("Edge image would follow the Testing package feed")
    return {"schema": 1, "fedora": 44, "profile": "fedora-kde", "models": ["apple,j700"],
            "signing_run": input_receipt["signing_run"],
            "replacement_signing_run": input_receipt["replacement_signing_run"],
            "replacement_mesa": input_receipt["replacement_mesa"], "files": exact,
            "installed_edge_packages": {key: signed[key] for key in sorted(set(selected))}}


if __name__ == "__main__":
    root, boot, receipt, output = map(Path, sys.argv[1:])
    output.write_text(json.dumps(proof(root, boot, json.loads(receipt.read_text())), indent=2) + "\n")
