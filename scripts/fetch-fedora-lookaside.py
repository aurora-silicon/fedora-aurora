#!/usr/bin/env python3
"""Fetch the inputs of a recipe imported from Fedora dist-git into its SOURCES.

`sources` is Fedora's lookaside list ("SHA512 (file) = digest"); each archive
comes from Fedora's lookaside cache and must match its SHA-512. distgit.json
names files kept out of this repository (Fedora's API keys) and their SHA-256;
they come from the pinned dist-git commit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

LOOKASIDE = 'https://src.fedoraproject.org/repo/pkgs/rpms/{name}/{file}/sha512/{digest}/{file}'
RAW = 'https://src.fedoraproject.org/rpms/{name}/raw/{commit}/f/{file}'
LINE = re.compile(r'^SHA512 \(([A-Za-z0-9._+-]+)\) = ([0-9a-f]{128})$')


def safe(name):
    if Path(name).name != name or name in ('', '.', '..'):
        raise SystemExit(f'unsafe file name {name!r}')
    return name


def digest(path, algorithm):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def download(url, target, algorithm, expected):
    if target.exists() and digest(target, algorithm) == expected:
        return
    partial = target.with_name(target.name + '.part')
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
            if digest(partial, algorithm) != expected:
                raise ValueError(f'{target.name}: {algorithm} mismatch')
            partial.replace(target)
            return
        except Exception as error:  # noqa: BLE001 - retried, then reported
            partial.unlink(missing_ok=True)
            if attempt == 4:
                raise SystemExit(f'{target.name}: {error} ({url})')
            time.sleep(10 * (attempt + 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', type=Path, help='rpmbuild SOURCES directory holding distgit.json and sources')
    args = parser.parse_args()
    pin = json.loads((args.sources / 'distgit.json').read_text())
    name = urllib.parse.urlparse(pin['repository']).path.rsplit('/', 1)[-1].removesuffix('.git')
    if not re.fullmatch(r'[0-9a-f]{40}', pin['commit']) or not re.fullmatch(r'[A-Za-z0-9._+-]+', name):
        raise SystemExit('distgit.json: bad commit or repository')
    for line in (args.sources / 'sources').read_text().splitlines():
        match = LINE.fullmatch(line.strip())
        if not match:
            raise SystemExit(f'sources: unexpected line {line!r}')
        file, sha512 = safe(match[1]), match[2]
        download(LOOKASIDE.format(name=name, file=file, digest=sha512), args.sources / file, 'sha512', sha512)
        print(f'{file}: sha512 ok')
    for file, sha256 in sorted(pin.get('fetch', {}).items()):
        download(RAW.format(name=name, commit=pin['commit'], file=safe(file)), args.sources / file, 'sha256', sha256)
        print(f'{file}: sha256 ok')


if __name__ == '__main__':
    main()
