#!/usr/bin/env python3
"""Verify the inventory of an authenticated Fedora 45 Testing release for Edge."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

import edgelib
import fedoralib


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package_digests(manifest, checksums):
    if (manifest['channel'] != 'testing' or manifest['fedora'] != 45
            or manifest['architecture'] != 'aarch64' or manifest['dry_run'] is not False):
        raise ValueError('Edge requires a real Fedora 45 Testing base')
    packages = {row['filename']: row['sha256'] for row in manifest['packages']}
    if (not packages or len(packages) != len(manifest['packages'])
            or not packages.items() <= checksums.items()):
        raise ValueError('the Fedora 45 base files differ from the authenticated manifest')
    return packages


def native_receipts(builds):
    origins = {}
    for receipt in builds['receipts']:
        if receipt.get('fedora', 44) == 45 and receipt.get('succeeded') is True:
            for file in receipt['artifacts']:
                asset = re.sub(r'[^A-Za-z0-9._-]', '.', file['filename'])
                origins.setdefault(asset, []).append(receipt)
    return origins


def verify_index(manifest, builds, checksums, downloaded, prior=None, same_recipe=None):
    packages = package_digests(manifest, checksums)
    binaries = {name for name in downloaded if edgelib.binary_rpm(name)}
    if set(packages) != binaries or not downloaded <= checksums.keys():
        raise ValueError('the Fedora 45 base files differ from the authenticated manifest')
    origins = native_receipts(builds)
    pending = packages.keys() - origins.keys()
    current_commit = builds.get('publishing_commit')
    seen = set()
    while pending and prior is not None and builds.get('base_release'):
        tag = fedoralib.snapshot(builds['base_release'], 45)
        if tag in seen or len(seen) >= 30:
            raise ValueError('cyclic or excessive Fedora 45 Testing base history')
        seen.add(tag)
        older_packages, builds = prior(tag)
        if any(older_packages.get(asset) != packages[asset] for asset in pending):
            raise ValueError('a carried Fedora 45 RPM differs from its authenticated predecessor')
        for asset, receipts in native_receipts(builds).items():
            if asset not in pending:
                continue
            if len(receipts) != 1 or not same_recipe(current_commit, builds['publishing_commit'], receipts[0]):
                raise ValueError('a carried Fedora 45 RPM lacks matching authenticated recipe inputs')
            origins[asset] = receipts
            pending.remove(asset)
    if pending or any(len(origins.get(asset, ())) != 1 for asset in packages):
        raise ValueError('a Fedora 45 base RPM lacks an unambiguous native build receipt')
    recipes = {origins[asset][0]['package'] for asset in packages}
    if not {'kernel-aurora', 'mesa-aurora', 'mesa-aurora-fex-guest', 'aurora-flatpak-gl'} <= recipes:
        raise ValueError('the Fedora 45 base lacks the full kernel or Mesa family')


def snapshot_metadata(directory):
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
    return json.loads(manifest.read_text()), indexed, checksums


def authenticate_prior(repository, tag, scratch):
    directory = scratch / tag
    subprocess.run(['gh', 'release', 'download', tag, '--repo', repository, '--dir', str(directory),
                    '--pattern', 'manifest.json', '--pattern', 'builds.json', '--pattern', 'SHA256SUMS'],
                   check=True, timeout=45)
    manifest, builds, checksums = snapshot_metadata(directory)
    proof = subprocess.check_output([
        'gh', 'attestation', 'verify', str(directory / 'manifest.json'), '--repo', repository,
        '--signer-workflow', f'{repository}/.github/workflows/publish.yml', '--source-ref', 'refs/heads/main',
        '--source-digest', builds['publishing_commit'], '--deny-self-hosted-runners', '--format', 'json',
    ], timeout=45)
    statements = ({(item['name'], item['digest']['sha256'])
                   for item in row['verificationResult']['statement']['subject']} for row in json.loads(proof))
    if not any(checksums.items() <= statement for statement in statements):
        raise ValueError('the predecessor attestation does not cover all Fedora 45 assets')
    return package_digests(manifest, checksums), builds


def unchanged_recipe(current, previous, receipt, scratch):
    name = receipt['package']
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name):
        raise ValueError('invalid Fedora package recipe name')
    pins = []
    for commit in (current, previous):
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('invalid Fedora Testing publication commit')
        directory = scratch / commit / name
        if not directory.exists():
            directory.mkdir(parents=True)
            archive = subprocess.check_output(['git', '-C', str(ROOT), 'archive', commit, 'sources.json',
                                              f'packages/{name}'], timeout=30)
            with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
                contents.extractall(directory, filter='data')
        if fedoralib.recipe_inputs(directory, name, 45) != receipt.get('recipe_inputs'):
            return False
        pins.append(fedoralib.sources(directory, 45).get(name))
    return pins[0] == pins[1]


def verify(directory, repository=None):
    manifest, indexed, checksums = snapshot_metadata(directory)
    files = list(directory.glob('*.rpm'))
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError('the Fedora 45 base contains an unsafe RPM path')
    with tempfile.TemporaryDirectory(prefix='edge-f45-predecessors-', dir=directory.parent) as scratch:
        prior = (lambda tag: authenticate_prior(repository, tag, Path(scratch))) if repository else None
        verify_index(manifest, indexed, checksums, {path.name for path in files}, prior,
                     lambda current, previous, receipt: unchanged_recipe(current, previous, receipt, Path(scratch)))
    return {'packaging_commit': indexed['publishing_commit'], 'manifest_sha256': checksums['manifest.json'],
            'builds_sha256': checksums['builds.json']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', type=Path)
    parser.add_argument('--repository')
    args = parser.parse_args()
    print(json.dumps(verify(args.base, args.repository)))
