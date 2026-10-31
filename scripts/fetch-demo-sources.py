#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage the immutable public demo build inputs for rpmbuild."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('sources', nargs='+')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
pins = json.loads((ROOT / 'demos/sources.json').read_text())
a.output.mkdir(parents=True, exist_ok=True)
for name in a.sources:
    pin = pins[name]
    target = a.output / (name + '-' + pin['commit'] + '.tar.gz')
    if pin.get('local_archive'):
        local = ROOT / 'demos' / pin['local_archive']
        with local.open('rb') as src:
            if hashlib.file_digest(src, 'sha256').hexdigest() != pin['sha256']:
                raise SystemExit(name + ': source-only archive SHA-256 mismatch')
        if not target.exists():
            import shutil
            shutil.copyfile(local, target)
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=a.output) as temp:
            with urllib.request.urlopen(pin['source_url'], timeout=120) as src:
                while chunk := src.read(1024 * 1024):
                    temp.write(chunk)
            temp.flush()
            with open(temp.name, 'rb') as src:
                if hashlib.file_digest(src, 'sha256').hexdigest() != pin['sha256']:
                    raise SystemExit(name + ': download SHA-256 mismatch')
            import shutil
            shutil.copyfile(temp.name, target)
    with target.open('rb') as src:
        if hashlib.file_digest(src, 'sha256').hexdigest() != pin['sha256']:
            raise SystemExit(name + ': cached SHA-256 mismatch')
    print(target)
