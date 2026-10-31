#!/usr/bin/env python3
"""Merge a native build delta with an authenticated, complete RPM snapshot."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def asset_name(filename):
    """The name GitHub stored a release asset under: other characters
    become '.'. A snapshot signed before sign-repository.py used these
    names lists aura-1.0.0~b1-... while its asset is aura-1.0.0.b1-...."""
    return re.sub(r'[^A-Za-z0-9._-]', '.', filename)


def metadata(path):
    row = subprocess.check_output(['rpm', '-qp', '--qf', '%{NAME}\t%{ARCH}\t%{SOURCERPM}\n', str(path)],
                                  text=True).strip().split('\t')
    if len(row) != 3 or row[1] not in ('aarch64', 'noarch') or not row[2].endswith(('.src.rpm', '.nosrc.rpm')):
        raise ValueError(f'Unsupported binary RPM: {path.name}')
    return tuple(row)


def expected_sources():
    return {subprocess.check_output([
        'rpmspec', '--srpm', '-q', '--qf', '%{NAME}-%{VERSION}-%{RELEASE}.%|NOSOURCE?{no}:{}|src.rpm', str(spec),
    ], text=True).strip() for spec in (ROOT / 'packages').glob('*/*.spec')}


def verify_signature(path, database):
    output = subprocess.check_output([
        'rpmkeys', '--dbpath', str(database), '--checksig', '--verbose', str(path),
    ], text=True)
    if not any(re.search(r'\bsignature\b.*:\s*OK\s*$', line, re.I) for line in output.splitlines()):
        raise ValueError(f'Base RPM has no authenticated signature: {path.name}')


def verify_base(directory, key, fingerprint):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('signing_key') != fingerprint:
        raise ValueError('The base snapshot names another signing key')
    entries = manifest['packages']
    names = {asset_name(row['filename']) for row in entries}
    if len(names) != len(entries) or names != {path.name for path in directory.glob('*.rpm') if not path.name.endswith(('.src.rpm', '.nosrc.rpm'))}:
        raise ValueError('The base RPM inventory differs from its manifest')
    with tempfile.TemporaryDirectory(prefix='aurora-base-rpm-keys-') as temporary:
        subprocess.run(['rpmkeys', '--dbpath', temporary, '--import', str(key)], check=True)
        for entry in entries:
            path = directory / asset_name(entry['filename'])
            if path.is_symlink() or path.parent != directory or path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
                raise ValueError(f'Base package checksum mismatch: {path.name}')
            verify_signature(path, temporary)


class IncompleteSnapshot(ValueError):
    def __init__(self, missing, unexpected):
        super().__init__(f'Incomplete or stale snapshot; missing={sorted(missing)}, unexpected={sorted(unexpected)}')
        self.missing = missing


def assemble(base, candidates, output, expected):
    fresh = {}
    for path in sorted(candidates.glob('*.rpm')):
        if path.name.endswith(('.src.rpm', '.nosrc.rpm')):
            continue
        if path.is_symlink():
            raise ValueError('RPM input is a symlink')
        name, arch, source = metadata(path)
        if (name, arch) in fresh:
            raise ValueError(f'Duplicate candidate package: {name}.{arch}')
        fresh[name, arch] = (path, source)
    if not fresh:
        raise ValueError('No candidate RPMs')
    rebuilt = {source.rsplit('-', 2)[0] for _, source in fresh.values()}
    selected = {}
    for path in sorted(base.glob('*.rpm')) if base else []:
        if path.name.endswith(('.src.rpm', '.nosrc.rpm')):
            continue
        name, arch, source = metadata(path)
        if source.rsplit('-', 2)[0] not in rebuilt:
            if (name, arch) in selected:
                raise ValueError(f'Duplicate base package: {name}.{arch}')
            selected[name, arch] = (path, source)
    selected.update(fresh)
    actual = {source for _, source in selected.values()}
    if actual != expected:
        raise IncompleteSnapshot(expected - actual, actual - expected)
    output.mkdir()
    for path, _ in selected.values():
        shutil.copyfile(path, output / path.name)
    return sorted(path.name for path, _ in selected.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--missing-output', type=Path,
                        help='on an incomplete set, write the package names that need a native build')
    args = parser.parse_args()
    if args.base:
        verify_base(args.base, ROOT / 'keys/RPM-GPG-KEY-aurora', (ROOT / 'keys/fingerprint.txt').read_text().strip())
    try:
        names = assemble(args.base, args.candidates, args.output, expected_sources())
    except IncompleteSnapshot as error:
        if args.missing_output:
            args.missing_output.write_text(' '.join(sorted(n.rsplit('-', 2)[0] for n in error.missing)) + '\n')
        raise
    print(f'Assembled {len(names)} RPMs covering every current source recipe')


if __name__ == '__main__':
    main()
