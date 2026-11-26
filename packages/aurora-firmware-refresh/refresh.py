#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Add firmware from the installer archive without replacing live files."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
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


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# The secure boot checks below match aurora-installer's aurora-wifi-firmware
# (aurora-installer#248), which this package's pinned helpers predate.

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


def read_pin(status):
    """aurora-secboot's vendor firmware pin as the file holds it, or None
    when nothing is pinned."""
    try:
        return (Path(status["key_dir"]) / SECBOOT_PIN).read_text().strip()
    except FileNotFoundError:
        return None


def cpio_files(data):
    """{name: (mode, bytes)} of the files in a newc archive, hard links
    resolved; directories are left out and anything else is refused."""
    entries, bodies, off = [], {}, 0
    while True:
        off = (off + 3) & ~3
        head = data[off:off + 110]
        if len(head) < 110 or head[:6] not in (b"070701", b"070702"):
            raise Refused("firmware.cpio is not a newc archive")
        try:
            fields = [int(head[6 + 8 * i:14 + 8 * i], 16) for i in range(13)]
            name = data[off + 110:off + 110 + fields[11] - 1].decode("ascii")
        except ValueError:
            raise Refused("firmware.cpio has a malformed header") from None
        inode, mode, size = fields[0], fields[1], fields[6]
        off = (off + 110 + fields[11] + 3) & ~3
        if name == "TRAILER!!!":
            return {n: (m, bodies[i]) for n, i, m in entries}
        body = data[off:off + size]
        if len(body) != size:
            raise Refused("firmware.cpio is truncated")
        off += size
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise Refused(f"firmware.cpio holds {name}, which is not a file")
        # A hard link's data is in one of its entries; the others are empty.
        if size or inode not in bodies:
            bodies[inode] = body
        entries.append((name, inode, mode & 0o777))


def tar_files(path):
    """{name: (mode, bytes)} of firmware.tar's files, hard links resolved."""
    out = {}
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            source, hops = member, 0
            while source.islnk() and hops < 64:
                source, hops = archive.getmember(source.linkname), hops + 1
            if not source.isfile():
                raise Refused(f"firmware.tar holds {member.name}, which is not a file")
            out[member.name] = (source.mode & 0o777, archive.extractfile(source).read())
    return out


def check_vendorfw(vendorfw, pin):
    """Refuse unless vendorfw/ is the package aurora-secboot's pin names:
    firmware.cpio, the only part a signed boot uses, has the pinned digest,
    and firmware.tar and manifest.txt, which the rebuild keeps files from,
    hold what it holds."""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", pin or ""):
        raise Refused(f"aurora-secboot's vendor firmware pin is {pin or 'empty'!r}, not an archive digest: "
                      "signed boots trust no archive, so a new one needs the owner to remove the pin")
    try:
        data = (vendorfw / "firmware.cpio").read_bytes()
    except OSError as error:
        raise Refused(f"cannot read {vendorfw / 'firmware.cpio'}: {error}") from None
    if "sha256:" + sha256(data) != pin:
        raise Refused(f"{vendorfw / 'firmware.cpio'} is not the archive aurora-secboot's pin names: "
                      "signed boots refuse it, and nothing is built on it")
    files = cpio_files(data)
    _, packed = files.pop("vendorfw/.vendorfw.manifest", (None, None))
    try:
        if packed is None or (vendorfw / "manifest.txt").read_bytes() != packed:
            raise Refused(f"{vendorfw / 'manifest.txt'} is not the manifest in the pinned firmware.cpio")
        if {f"vendorfw/{k}": v for k, v in tar_files(vendorfw / "firmware.tar").items()} != files:
            raise Refused(f"{vendorfw / 'firmware.tar'} does not hold what the pinned firmware.cpio holds")
    except (OSError, KeyError, tarfile.TarError) as error:
        raise Refused(f"{vendorfw} does not read as the pinned package: {error}") from None


def rebind_secure_boot(esp, digest, *, cli=SECBOOT, run=subprocess.run):
    """Make aurora-secboot's pin and UKIs name the firmware.cpio this
    refresh built (digest). The pin is the only source of the binding a
    signed boot checks, so it follows only that archive, and only when the
    ESP holds exactly it; then each UKI is rebuilt, as kernel-install does.
    Without a pin, aurora-secboot pins on its next build."""
    secboot = secure_boot(esp, cli, run)
    if secboot is None:
        return
    tool, status = secboot
    pin = Path(status["key_dir"]) / SECBOOT_PIN
    if read_pin(status) is not None:
        try:
            on_esp = sha256((esp / "vendorfw" / "firmware.cpio").read_bytes())
        except OSError as error:
            on_esp = f"unreadable ({error})"
        if on_esp != digest:
            raise Refused("the firmware is installed, but the ESP's firmware.cpio is not the one this refresh "
                          "built, so it is not pinned: signed boots refuse it")
        partial = pin.with_name(f".{SECBOOT_PIN}.new")
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as file:
            file.write(f"sha256:{digest}\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(partial, pin)
        print(f"Pinned the new vendor firmware for secure boot in {pin}.")
    for image in status.get("ukis", []):
        if not image.get("kernel"):
            continue
        # The kernel-install hook: it builds the UKI and, on the secure
        # path, the boot loader copy too.
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
    # The rebuild keeps every file of the ESP's package, so on the secure
    # path that package must be the one aurora-secboot pinned.
    secboot = secure_boot(esp, cli, run)
    pin = read_pin(secboot[1]) if secboot else None
    if pin is not None:
        check_vendorfw(live, pin)
        print("Secure boot: the files this adds come from the installer's archive on the ESP "
              "(asahi/all_firmware.tar.gz), which nothing can check; refreshing trusts it, "
              "and the pin follows the new firmware.cpio.")
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
        built = sha256((staged / "firmware.cpio").read_bytes())
        if check:
            print(f"Would add {len(added)} firmware files and keep {len(original)}.")
            return len(added)

        require_space(esp, tree_size(staged))
        backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix="firmware-refresh-", dir=backup_root))
        copy_verified(live, backup / "vendorfw")
        commit(esp, [(staged, live)], backup)
        print(f"Added {len(added)} firmware files and kept {len(original)}.")
        rebind_secure_boot(esp, built, cli=cli, run=run)
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
