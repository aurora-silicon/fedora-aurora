#!/usr/bin/env python3
"""Record and compare the main RPM header and payload across package signing."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import struct

HEADER_MAGIC = bytes.fromhex("8eade80100000000")


def rpm_content(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"RPM is not a regular file: {path.name}")
    with path.open("rb") as rpm:
        lead = rpm.read(96)
        if len(lead) != 96 or lead[:4] != bytes.fromhex("edabeedb"):
            raise ValueError(f"Invalid RPM lead: {path.name}")
        sig = rpm.read(16)
        if len(sig) != 16 or sig[:8] != HEADER_MAGIC:
            raise ValueError(f"Invalid RPM signature header: {path.name}")
        entries, data = struct.unpack(">II", sig[8:])
        header = (rpm.tell() + entries * 16 + data + 7) & ~7
        if header + 16 >= path.stat().st_size:
            raise ValueError(f"RPM signature header exceeds the file: {path.name}")
        rpm.seek(header)
        if rpm.read(8) != HEADER_MAGIC:
            raise ValueError(f"Invalid main RPM header: {path.name}")
        rpm.seek(header)
        content = hashlib.file_digest(rpm, "sha256").hexdigest()
        rpm.seek(0)
        return {
            "main_header_and_payload_sha256": content,
            "sha256": hashlib.file_digest(rpm, "sha256").hexdigest(),
            "bytes": path.stat().st_size,
        }


def inventory(directory):
    result = {path.name: rpm_content(path) for path in sorted(directory.glob("*.rpm"))}
    if not result:
        raise ValueError("No RPMs to verify")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rpms", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    current = inventory(args.rpms)
    result = {"schema": 1, "rpms": current}
    if args.compare:
        old = json.loads(args.compare.read_text())["rpms"]
        if old.keys() != current.keys():
            raise ValueError("Signing changed the RPM inventory")
        for name, record in current.items():
            if record["main_header_and_payload_sha256"] != old[name]["main_header_and_payload_sha256"]:
                raise ValueError(f"Signing changed the RPM main header or payload: {name}")
        result["unsigned_rpms"] = old
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
