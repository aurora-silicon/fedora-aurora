#!/usr/bin/env python3
"""Sign a tested RPM set and prepare static DNF repository metadata."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def archive_metadata(site, snapshot):
    """Retain the exact signed DNF metadata without duplicating package assets."""
    if not re.fullmatch(r'testing-[A-Za-z0-9._-]+', snapshot):
        raise ValueError('Invalid immutable snapshot tag')
    repository = site / '44/testing/aarch64'
    repodata = repository / 'repodata'
    if any(path.is_symlink() for path in (site, site / '44', site / '44/testing', repository, repodata)):
        raise ValueError('Metadata directories must not be links')
    files = [site / 'RPM-GPG-KEY-aurora', repository / 'manifest.json',
             repodata / 'repomd.xml', repodata / 'repomd.xml.asc']
    ns = {'r': 'http://linux.duke.edu/metadata/repo'}
    repomd = repodata / 'repomd.xml'
    if repomd.is_symlink() or not repomd.is_file() or repomd.stat().st_size > 2 * 1024**2:
        raise ValueError('Invalid repository metadata index')
    records = ET.fromstring(repomd.read_bytes()).findall('r:data', ns)
    if not 1 <= len(records) <= 128:
        raise ValueError('Unexpected repository metadata inventory')
    for record in records:
        location = record.find('r:location', ns)
        checksum = record.find('r:checksum', ns)
        size = record.find('r:size', ns)
        relative = '' if location is None else location.get('href', '')
        if (not re.fullmatch(r'repodata/[A-Za-z0-9_.+-]+', relative)
                or checksum is None or checksum.get('type') != 'sha256'
                or not re.fullmatch(r'[a-f0-9]{64}', checksum.text or '')
                or size is None or not (size.text or '').isdigit()):
            raise ValueError('Unsafe repository metadata record')
        path = repository / relative
        if path in files or path.is_symlink() or not path.is_file():
            raise ValueError('Missing or duplicate repository metadata')
        if not 0 < path.stat().st_size == int(size.text) <= 32 * 1024**2:
            raise ValueError('Repository metadata exceeds its budget')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != checksum.text:
                raise ValueError('Repository metadata checksum mismatch')
        files.append(path)
    if (any(path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 32 * 1024**2
            for path in files) or sum(path.stat().st_size for path in files) > 64 * 1024**2):
        raise ValueError('Unsafe metadata snapshot')
    archive = site / f'repository-metadata-{snapshot}.tar.gz'
    with archive.open('xb') as output, gzip.GzipFile(fileobj=output, filename='', mtime=0, mode='wb') as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as bundle:
            for path in sorted(files):
                entry = tarfile.TarInfo(path.relative_to(site).as_posix())
                entry.size = path.stat().st_size
                entry.mode = 0o644
                entry.mtime = 0
                with path.open('rb') as source:
                    bundle.addfile(entry, source)
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpms", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-base", required=True)
    parser.add_argument("--snapshot", help="Immutable testing tag whose signed metadata should be retained")
    parser.add_argument("--credentials-stdin", action="store_true")
    parser.add_argument("--dry-run-public-key", type=Path,
                        help="sign with a throwaway key whose public half is given here (dry runs only)")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; use a fresh repository snapshot")
    if args.snapshot and not re.fullmatch(r'testing-[A-Za-z0-9._-]+', args.snapshot):
        parser.error('invalid immutable snapshot tag')
    url = urllib.parse.urlsplit(args.asset_base)
    if url.scheme != "https" or not url.hostname or url.query or url.fragment:
        parser.error("asset base must be an immutable HTTPS release directory")
    if args.snapshot and url.path.rstrip('/').rsplit('/', 1)[-1] != args.snapshot:
        parser.error('snapshot tag does not match the immutable asset base')
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
    public_key = ROOT / "keys/RPM-GPG-KEY-aurora"
    expected = (ROOT / "keys/fingerprint.txt").read_text().strip()
    if args.dry_run_public_key:
        # Proves the pipeline without the release key; deployment verifies
        # against keys/fingerprint.txt and rejects this output.
        public_key = args.dry_run_public_key
        expected = subprocess.check_output(
            ["gpg", "--batch", "--with-colons", "--import-options", "show-only", "--import", str(public_key)],
            text=True).split("fpr:::::::::", 1)[1].split(":", 1)[0]
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
        run("rpmkeys", "--import", str(public_key))
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
        shutil.copyfile(public_key, args.output / "RPM-GPG-KEY-aurora")
        (destination / "manifest.json").write_text(json.dumps({
            "schema": 1, "channel": "testing", "fedora": 44, "architecture": "aarch64",
            "signing_key": expected, "asset_base": args.asset_base, "dry_run": bool(args.dry_run_public_key),
            "packages": manifest,
        }, indent=2) + "\n")
        if args.snapshot:
            archive = archive_metadata(args.output, args.snapshot)
            run(*gpg, "--local-user", expected, "--armor", "--detach-sign", str(archive))
            run(*gpg, "--verify", str(archive) + ".asc", str(archive))
        run("gpgconf", "--homedir", str(home), "--kill", "gpg-agent")
    print(f"Prepared {len(manifest)} signed RPMs and verified repository metadata")


if __name__ == "__main__":
    main()
