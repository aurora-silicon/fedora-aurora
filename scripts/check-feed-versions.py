#!/usr/bin/env python3
"""Refuse a package set that would move any RPM to an older version.

Each side is a directory of binary RPMs (read with `rpm -qp`) or a DNF
repository directory containing repodata/repomd.xml (read without rpm). EVRs
compare with RPM's rules per (name, arch), so dnf would never see the new set
as a downgrade. Removed packages are reported without failing.
"""
import argparse
import gzip
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import updatelib as lib  # noqa: E402

REPO = '{http://linux.duke.edu/metadata/repo}'
COMMON = '{http://linux.duke.edu/metadata/common}'


def decompress(data):
    if data[:2] == b'\x1f\x8b':
        return gzip.decompress(data)
    if data[:4] == b'\x28\xb5\x2f\xfd':
        return subprocess.run(['zstd', '-dc'], input=data, capture_output=True, check=True).stdout
    if data[:6] == b'\xfd7zXZ\x00':
        import lzma
        return lzma.decompress(data)
    return data


def repository_versions(directory):
    repomd = ET.parse(directory / 'repodata/repomd.xml').getroot()
    primary = next(data for data in repomd.findall(f'{REPO}data') if data.get('type') == 'primary')
    location = primary.find(f'{REPO}location').get('href')
    expected = primary.find(f'{REPO}checksum').text
    path = directory / location
    if lib.sha256_file(path) != expected:
        raise ValueError(f'{path}: checksum does not match repomd.xml')
    versions = {}
    root = ET.fromstring(decompress(path.read_bytes()))
    for package in root.findall(f'{COMMON}package'):
        name = package.find(f'{COMMON}name').text
        arch = package.find(f'{COMMON}arch').text
        if arch == 'src':
            continue
        version = package.find(f'{COMMON}version')
        evr = (version.get('epoch') or '0', version.get('ver'), version.get('rel'))
        key = f'{name}.{arch}'
        if key not in versions or lib.rpm_evr_compare(evr, versions[key]) > 0:
            versions[key] = evr
    return versions


def rpm_versions(directory):
    versions = {}
    for path in sorted(directory.glob('*.rpm')):
        if path.name.endswith(('.src.rpm', '.nosrc.rpm')):
            continue
        row = subprocess.check_output(['rpm', '-qp', '--qf', '%{NAME}\t%{ARCH}\t%{EPOCHNUM}\t%{VERSION}\t%{RELEASE}',
                                       str(path)], text=True).split('\t')
        key = f'{row[0]}.{row[1]}'
        evr = (row[2], row[3], row[4])
        if key not in versions or lib.rpm_evr_compare(evr, versions[key]) > 0:
            versions[key] = evr
    return versions


def versions(source):
    source = Path(source)
    return repository_versions(source) if (source / 'repodata/repomd.xml').exists() else rpm_versions(source)


def label(evr):
    epoch, version, release = evr
    return f'{epoch + ":" if epoch not in ("", "0") else ""}{version}-{release}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', required=True)
    parser.add_argument('--new', required=True)
    parser.add_argument('--allow-downgrade', action='store_true')
    parser.add_argument('--changes-output', type=Path,
                        help='write the number of changed, added and removed packages here')
    args = parser.parse_args()
    old, new = versions(args.old), versions(args.new)
    downgraded, removed, added = lib.regressions(old, new, lib.rpm_evr_compare)
    changed = sorted(key for key in old.keys() & new.keys() if old[key] != new[key])
    for key in changed:
        print(f'{key}: {label(old[key])} -> {label(new[key])}')
    for key in added:
        print(f'{key}: new at {label(new[key])}')
    for key in removed:
        print(f'{key}: removed (was {label(old[key])})')
    if args.changes_output:
        args.changes_output.write_text(f'{len(changed) + len(added) + len(removed)}\n')
    if downgraded:
        for key, before, after in downgraded:
            print(f'DOWNGRADE {key}: {label(before)} -> {label(after)}', file=sys.stderr)
        if not args.allow_downgrade:
            raise SystemExit('The candidate would downgrade installed packages; see above.')
    print(f'{len(changed)} changed, {len(added)} added, {len(removed)} removed, {len(downgraded)} downgraded')


if __name__ == '__main__':
    main()
