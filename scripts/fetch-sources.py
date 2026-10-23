#!/usr/bin/env python3
"""Fetch immutable source archives and check their recorded SHA-256 identities."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))
import updatelib  # noqa: E402

# Verified copies of pinned archives (track-sources.yml keeps it complete).
# Every byte is still checked against sources.json; the mirror only avoids
# codeload rate limits. Set AURORA_SOURCE_MIRROR= (empty) to skip it.
MIRROR = "https://github.com/aurora-silicon/fedora-aurora/releases/download/source-cache"


def fetch(name, destination):
    record = json.loads((ROOT / "sources.json").read_text())[name]
    expected = record.get("sha256")
    if not expected:
        raise ValueError(f"{name}: source archive has not been hash-pinned")
    destination.mkdir(parents=True, exist_ok=True)
    filename = record.get("archive_file", f"{name}-{record['commit']}.tar.gz")
    if not isinstance(filename, str) or Path(filename).name != filename or filename in ("", ".", "..") or "\\" in filename:
        raise ValueError(f"{name}: unsafe source archive filename")
    target = destination / filename
    cache = ROOT / "cache/sources" / target.name
    if not target.exists() and cache.exists() and cache != target:
        with cache.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected:
                raise ValueError(f"{name}: source cache checksum mismatch")
        shutil.copyfile(cache, target)
    if not target.exists():
        mirror = os.environ.get("AURORA_SOURCE_MIRROR", MIRROR)
        urls = ([f"{mirror.rstrip('/')}/{filename}"] if mirror else []) + [record["source_url"]]
        try:
            updatelib.download(urls, target, sha256=expected, token=os.environ.get("GH_TOKEN"))
        except RuntimeError as error:
            raise ValueError(f"{name}: downloaded archive checksum mismatch or source unavailable: {error}") from error
    with target.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != expected:
            raise ValueError(f"{name}: cached archive checksum mismatch")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packages", nargs="+")
    parser.add_argument("--output", type=Path, default=ROOT / "cache/sources")
    args = parser.parse_args()
    for name in args.packages:
        print(fetch(name, args.output))
