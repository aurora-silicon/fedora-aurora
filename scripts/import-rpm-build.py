#!/usr/bin/env python3
"""Accept native CI artifacts only when their build inputs match merged recipes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import subprocess

SHARED = ('.github/workflows/rpms.yml', 'scripts/build-rpm',
          'scripts/fetch-sources.py', 'scripts/build-receipt.py', 'scripts/build-flatpak-gl-repo')
# Recipes whose payload is x86 code for FEX guests are built on x86_64.
X86_BUILDER = '# aurora-builder: x86_64'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def import_build(root, metadata, artifacts, output, repository, matching_only=False, packages=None):
    commit = metadata.get('head_sha', '')
    if (metadata.get('conclusion') != 'success' or metadata.get('head_repository', {}).get('full_name') != repository
            or metadata.get('event') not in ('push', 'workflow_dispatch')
            or metadata.get('path') != '.github/workflows/rpms.yml' or not re.fullmatch('[0-9a-f]{40}', commit)):
        raise ValueError('Not a successful native build from this repository')
    ancestry = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', commit, 'HEAD'])
    if ancestry.returncode:
        raise ValueError('Build commit has not been merged into the publishing source')
    for name in SHARED:
        if git(root, 'rev-parse', f'{commit}:{name}') != git(root, 'rev-parse', f'HEAD:{name}'):
            raise ValueError(f'The native build tooling changed: {name}')
    previous = json.loads(git(root, 'show', f'{commit}:sources.json'))
    current = json.loads((root / 'sources.json').read_text())
    manifests = sorted(artifacts.glob('rpm-*/out/manifests/*.json'))
    if not manifests:
        raise ValueError('The build has no package receipts')
    selected = []
    accepted_receipts = []
    for receipt in manifests:
        data = json.loads(receipt.read_text())
        name = data.get('package', '')
        if not re.fullmatch('[a-z0-9][a-z0-9-]*', name) or receipt.parents[2].name != 'rpm-' + name:
            raise ValueError('Unexpected package receipt location')
        if packages is not None and name not in packages:
            continue
        directory = root / 'packages' / name
        recipe = directory / (name + '.spec')
        builder = 'x86_64' if recipe.is_file() and X86_BUILDER in recipe.read_text().splitlines() else 'aarch64'
        if data.get('succeeded') is not True or data.get('architecture') != builder:
            raise ValueError(f'Package did not complete a native {builder} build')
        if not directory.is_dir() or git(root, 'rev-parse', f'{commit}:packages/{name}') != git(root, 'rev-parse', f'HEAD:packages/{name}'):
            if matching_only:
                print(f'Skipping superseded package recipe: {name}', file=sys.stderr)
                continue
            raise ValueError(f'The package recipe changed: {name}')
        expected = {p.name: digest(p) for p in directory.iterdir() if p.is_file()}
        if data.get('recipe_inputs') != expected or previous.get(name) != current.get(name):
            if matching_only:
                print(f'Skipping superseded package inputs: {name}', file=sys.stderr)
                continue
            raise ValueError(f'The package inputs changed: {name}')
        packaged = receipt.parents[1]
        inventory = data.get('artifacts', [])
        recorded = set()
        for record in inventory:
            filename = record['filename']
            if Path(filename).name != filename or not filename.endswith('.rpm') or filename in recorded:
                raise ValueError('Unexpected artifact filename')
            recorded.add(filename)
            kind = 'srpms' if filename.endswith('.src.rpm') else 'rpms'
            path = packaged / kind / filename
            if path.is_symlink() or not path.is_file() or path.stat().st_size != record['bytes'] or digest(path) != record['sha256']:
                raise ValueError(f'CI artifact checksum mismatch: {filename}')
            selected.append((path, output / kind / filename))
        actual = {p.name for kind in ('rpms', 'srpms') for p in (packaged / kind).glob('*.rpm')}
        if recorded != actual or not any(not n.endswith('.src.rpm') for n in recorded) or not any(n.endswith('.src.rpm') for n in recorded):
            raise ValueError('Incomplete CI artifact inventory')
        accepted_receipts.append(receipt)
    if not accepted_receipts:
        raise ValueError('No native packages match the current merged inputs')
    selected.extend((receipt, output / 'manifests' / receipt.name) for receipt in accepted_receipts)
    for source, target in selected:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if digest(source) != digest(target):
                raise ValueError(f'Conflicting build artifacts: {target.name}')
        else:
            shutil.copyfile(source, target)
    return len(accepted_receipts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--matching-only', action='store_true',
                        help='Import only unchanged merged recipes; full snapshot assembly still requires every current recipe')
    parser.add_argument('--packages', nargs='+',
                        help='Import only these packages from the run (another run supplies the rest)')
    args = parser.parse_args()
    count = import_build(Path(__file__).resolve().parents[1], json.loads(args.metadata.read_text()),
                         args.artifacts, args.output, args.repository, args.matching_only,
                         set(args.packages) if args.packages else None)
    print(f'Accepted {count} native package build(s) with unchanged merged inputs')


if __name__ == '__main__':
    main()
