#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Add firmware from the installer archive without replacing live files."""
import argparse
import fcntl
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from asahi_firmware.core import FWFile
from asahi_firmware.update import update_firmware
from aurora_wifi_firmware import (
    Refused, check_package, commit, copy_verified, package_extras, parse_manifest,
    rebuild_vendorfw, require_space, system_esp, tree_size,
)


def manifest(directory):
    return parse_manifest((directory / "manifest.txt").read_text("ascii"))


def refresh(esp, *, check=False, backup_root=Path("/var/lib/aurora-rollback"),
            extract=update_firmware):
    source = esp / "asahi"
    live = esp / "vendorfw"
    if not (source / "all_firmware.tar.gz").is_file():
        print("No installer firmware archive; keeping the current firmware.")
        return 0
    original = manifest(live)
    original_extras = package_extras(live)
    with tempfile.TemporaryDirectory(prefix="aurora-firmware-refresh-") as directory:
        candidate, staged = (Path(directory) / name for name in ("candidate", "staged"))
        candidate.mkdir()
        staged.mkdir()
        extract(source, candidate)

        # An installed radio or speaker-tuning tool may have replaced these
        # paths. A generic refresh only owns names that are absent.
        new = manifest(candidate)
        with tarfile.open(candidate / "firmware.tar") as archive:
            added = {name: FWFile(name, archive.extractfile(name).read())
                     for name in sorted(new.keys() - original.keys())}
        if any(file.sha != new[name] for name, file in added.items()):
            raise Refused("the extracted archive disagrees with its manifest")
        if not added:
            print(f"Kept {len(original)} installed firmware files; no new files.")
            return 0

        rebuild_vendorfw(live, staged, added, added.__contains__)
        # Keep extra files, including boot firmware left by the installer or
        # the radio updater, even when they are outside firmware.tar.
        for name in original_extras:
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(live / name, target)
        check_package(live, staged, added, added.__contains__)
        if check:
            print(f"Would add {len(added)} firmware files and keep {len(original)}.")
            return len(added)

        require_space(esp, tree_size(staged))
        backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix="firmware-refresh-", dir=backup_root))
        copy_verified(live, backup / "vendorfw")
        commit(esp, [(staged, live)], backup)
        print(f"Added {len(added)} firmware files and kept {len(original)}.")
        return len(added)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the result without writing it")
    args = parser.parse_args()
    # Use the same writer lock as the installer's radio tool.
    try:
        with open("/run/lock/aurora-firmware.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with system_esp() as esp:
                refresh(esp, check=args.check)
    except (Refused, OSError, tarfile.TarError, ValueError) as error:
        print(f"aurora-firmware-refresh: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
