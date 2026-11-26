#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Add firmware from the installer archive without replacing live files."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
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


SECBOOT = "aurora-secboot"
SECBOOT_PIN = "vendorfw.sha256"


def secure_boot(esp, cli=SECBOOT, run=subprocess.run):
    """(aurora-secboot, its status) when it is set up for this ESP, else None."""
    tool = shutil.which(cli)
    if not tool:
        return None
    try:
        status = json.loads(run([tool, "status", "--json"], check=True, capture_output=True,
                                text=True).stdout)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        raise Refused(f"aurora-secboot status failed ({error})") from None
    if not status.get("config_present"):
        return None
    try:
        same = os.path.samefile(status["esp"], esp)
    except (KeyError, OSError):
        same = False
    if not same:
        print(f"aurora-secboot uses another ESP ({status.get('esp')}); its vendor firmware pin is "
              "left alone.", file=sys.stderr)
        return None
    return tool, status


def pin_path(status):
    """aurora-secboot's vendor firmware pin, when one is in place, else None."""
    path = Path(status["key_dir"]) / SECBOOT_PIN
    return path if path.exists() else None


def rebuild_ukis(tool, status, run=subprocess.run):
    """kernel-install's aurora-secboot step for each UKI: it builds the UKI
    and, on the secure path, the boot loader copy too. With no pin in place
    (the owner removed it), the first build pins the ESP's archive."""
    for image in status.get("ukis", []):
        if not image.get("kernel"):
            continue
        if run([tool, "hook", "add", image["kernel"]]).returncode:
            raise Refused(f"the firmware is installed, but the UKI of {image['kernel']} was not rebuilt; "
                          f"signed boots refuse the new firmware until 'aurora-secboot hook add "
                          f"{image['kernel']}' succeeds")


def refresh(esp, *, check=False, backup_root=Path("/var/lib/aurora-rollback"),
            extract=update_firmware, cli=SECBOOT, run=subprocess.run):
    source = esp / "asahi"
    live = esp / "vendorfw"
    if not (source / "all_firmware.tar.gz").is_file():
        print("No installer firmware archive; keeping the current firmware.")
        return 0
    # A signed boot unpacks only the vendor firmware aurora-secboot's pin
    # names, and the pin follows only verified files. What a refresh adds
    # comes from the installer's archive on the ESP and the ESP's own
    # package, which nothing can check, so with a pin in place the refresh
    # changes nothing: removing the pin is the owner's explicit acceptance.
    secboot = secure_boot(esp, cli, run)
    pin = pin_path(secboot[1]) if secboot else None
    refusal = (f"aurora-secboot's vendor firmware pin {pin} is in place, and a refresh adds files from the "
               f"ESP (asahi/all_firmware.tar.gz and the current vendorfw/) that nothing can check, so it "
               f"does not re-pin them and changes nothing. To accept what the ESP holds now, remove {pin} "
               f"and run aurora-firmware-refresh again: it then rebuilds the UKIs, which pin the new "
               f"archive.") if pin else None
    if refusal and not check:
        raise Refused(refusal)
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
            if refusal:
                print(f"Secure boot: {refusal}")
            return len(added)

        require_space(esp, tree_size(staged))
        backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix="firmware-refresh-", dir=backup_root))
        copy_verified(live, backup / "vendorfw")
        commit(esp, [(staged, live)], backup)
        print(f"Added {len(added)} firmware files and kept {len(original)}.")
        if secboot:
            rebuild_ukis(*secboot, run=run)
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
