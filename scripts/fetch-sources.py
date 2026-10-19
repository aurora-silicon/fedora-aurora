#!/usr/bin/env python3
"""Fetch immutable source archives and check their recorded SHA-256 identities."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


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
        pending = target.with_suffix(".download")
        with urllib.request.urlopen(record["source_url"], timeout=120) as source, pending.open("wb") as output:
            shutil.copyfileobj(source, output)
        with pending.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected:
                raise ValueError(f"{name}: downloaded archive checksum mismatch")
        pending.rename(target)
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
