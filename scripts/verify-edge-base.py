#!/usr/bin/env python3
"""Verify the inventory of an authenticated Fedora 45 Testing release for Edge."""

import argparse
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_index(manifest, builds, checksums, downloaded):
    if (manifest['channel'] != 'testing' or manifest['fedora'] != 45
            or manifest['architecture'] != 'aarch64' or manifest['dry_run'] is not False):
        raise ValueError('Edge requires a real Fedora 45 Testing base')
    packages = {row['filename']: row['sha256'] for row in manifest['packages']}
    if (not packages or len(packages) != len(manifest['packages']) or set(packages) != downloaded
            or not packages.items() <= checksums.items()):
        raise ValueError('the Fedora 45 base files differ from the authenticated manifest')
    origins = {}
    for receipt in builds['receipts']:
        if receipt.get('fedora', 44) == 45 and receipt.get('succeeded'):
            for file in receipt['artifacts']:
                asset = re.sub(r'[^A-Za-z0-9._-]', '.', file['filename'])
                origins.setdefault(asset, set()).add(receipt['package'])
    if any(len(origins.get(asset, ())) != 1 for asset in packages):
        raise ValueError('a Fedora 45 base RPM lacks an unambiguous native build receipt')
    recipes = {next(iter(origins[asset])) for asset in packages}
    if not {'kernel-aurora', 'mesa-aurora', 'mesa-aurora-fex-guest', 'aurora-flatpak-gl'} <= recipes:
        raise ValueError('the Fedora 45 base lacks the full kernel or Mesa family')


def verify(directory):
    checksums = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        checksum, name = line.split(maxsplit=1)
        name = name.lstrip('*')
        if name in checksums or not re.fullmatch(r'[0-9a-f]{64}', checksum):
            raise ValueError('invalid or repeated Fedora 45 asset checksum')
        checksums[name] = checksum
    manifest = directory / 'manifest.json'
    builds = directory / 'builds.json'
    for path in (manifest, builds):
        if checksums.get(path.name) != digest(path):
            raise ValueError(f'{path.name} is outside the authenticated asset list')
    indexed = json.loads(builds.read_text())
    commit = indexed['publishing_commit']
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('invalid Fedora 45 publication source')
    files = list(directory.glob('*.rpm'))
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError('the Fedora 45 base contains an unsafe RPM path')
    verify_index(json.loads(manifest.read_text()), indexed, checksums, {path.name for path in files})
    return {'packaging_commit': commit, 'manifest_sha256': checksums[manifest.name],
            'builds_sha256': checksums[builds.name]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', type=Path)
    print(json.dumps(verify(parser.parse_args().base)))
