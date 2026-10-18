#!/usr/bin/env python3
"""Sign a tested RPM set and prepare static DNF repository metadata."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpms", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-base", required=True)
    parser.add_argument("--credentials-stdin", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; use a fresh repository snapshot")
    url = urllib.parse.urlsplit(args.asset_base)
    if url.scheme != "https" or not url.hostname or url.query or url.fragment:
        parser.error("asset base must be an immutable HTTPS release directory")
    packages = sorted(args.rpms.glob("*.rpm"))
    if not packages:
        parser.error("no RPMs supplied")
    for package in packages:
        if package.is_symlink() or not re.fullmatch(r"[A-Za-z0-9_.+~-]+\.rpm", package.name):
            parser.error("unsafe RPM input")
    credentials = (json.load(sys.stdin) if args.credentials_stdin else {
        "key": os.environ["FEDORA_RPM_SIGNING_KEY"],
        "passphrase": os.environ["FEDORA_RPM_SIGNING_PASSPHRASE"],
    })
    expected = (ROOT / "keys/fingerprint.txt").read_text().strip()
    args.output.mkdir(parents=True)
    destination = args.output / "44/testing/aarch64"
    destination.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="aurora-signing-") as directory:
        home = Path(directory)
        passfile = home / "passphrase"
        passfile.write_text(credentials["passphrase"])
        passfile.chmod(0o600)
        gpg = ["gpg", "--no-options", "--homedir", str(home), "--batch",
               "--pinentry-mode", "loopback", "--passphrase-file", str(passfile)]
        run(*gpg, "--import", input=credentials["key"].encode(), stdout=subprocess.DEVNULL)
        listing = subprocess.check_output(gpg + ["--with-colons", "--list-secret-keys"], text=True)
        fingerprints = [line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr:")]
        if expected not in fingerprints:
            raise ValueError("signing key differs from the committed public key")
        run("rpmkeys", "--import", str(ROOT / "keys/RPM-GPG-KEY-aurora"))
        manifest = []
        for package in packages:
            target = destination / package.name
            shutil.copyfile(package, target)
            run("rpmsign", "--define", f"_gpg_path {home}",
                "--define", f"_openpgp_sign_id {expected}",
                "--define", f"_gpg_sign_cmd_extra_args --batch --pinentry-mode loopback --passphrase-file {passfile}",
                "--addsign", str(target))
            run("rpmkeys", "--checksig", str(target))
            with target.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            manifest.append({"filename": target.name, "sha256": digest, "bytes": target.stat().st_size})
        run("createrepo_c", "--checksum", "sha256", "--baseurl", args.asset_base.rstrip("/") + "/",
            str(destination))
        repomd = destination / "repodata/repomd.xml"
        run(*gpg, "--local-user", expected, "--armor", "--detach-sign", str(repomd))
        run(*gpg, "--verify", str(repomd) + ".asc", str(repomd))
        run("gpgconf", "--homedir", str(home), "--kill", "gpg-agent")
    shutil.copyfile(ROOT / "keys/RPM-GPG-KEY-aurora", args.output / "RPM-GPG-KEY-aurora")
    (destination / "manifest.json").write_text(json.dumps({
        "schema": 1, "channel": "testing", "fedora": 44, "architecture": "aarch64",
        "signing_key": expected, "asset_base": args.asset_base, "packages": manifest,
    }, indent=2) + "\n")
    print(f"Prepared {len(manifest)} signed RPMs and verified repository metadata")


if __name__ == "__main__":
    main()
