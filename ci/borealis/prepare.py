#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare checksum-pinned public inputs for system Mesa and its FEX provider."""
import hashlib
import gzip
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile

commit, checksum, release, kind, destination=sys.argv[1:]
assert re.fullmatch('[0-9a-f]{40}',commit)
assert re.fullmatch('[0-9a-f]{64}',checksum)
assert re.fullmatch(r'0\.[0-9]+',release)
assert kind in ('native','fex')
dest=pathlib.Path(destination).resolve()
assert not dest.exists()
for directory in ('SOURCES','SPECS','out','buildroot','tmp'):
    (dest/directory).mkdir(parents=True,exist_ok=True)
recipe=pathlib.Path(__file__).resolve().parent
repo=recipe.parents[1]

def fetch(url, path, expected):
    subprocess.run(['curl','--fail','--location','--retry','2','--max-time','600',
                    '--output',str(path)+'.part',url],check=True)
    part=pathlib.Path(str(path)+'.part')
    assert hashlib.sha256(part.read_bytes()).hexdigest()==expected, path.name
    part.rename(path)

archive=dest/'source.tar.gz'
fetch('https://codeload.github.com/aurora-silicon/mesa/tar.gz/'+commit,archive,checksum)
if kind=='native':
    unpack=dest/'unpack'
    unpack.mkdir()
    with tarfile.open(archive) as tar:
        assert all(m.name.startswith('mesa-'+commit+'/') or m.name=='mesa-'+commit for m in tar.getmembers())
        tar.extractall(unpack,filter='data')
    source=unpack/('mesa-'+commit)
    target=unpack/'mesa-26.3.0-devel'
    source.rename(target)
    subprocess.run(['tar','--sort=name','--mtime=@0','--owner=0','--group=0','--numeric-owner',
                    '-C',str(unpack),'-cJf',str(dest/'SOURCES/mesa-26.3.0-devel.tar.xz'),target.name],check=True)
    spec=(recipe/'mesa.spec.in').read_text().replace('@COMMIT@',commit).replace('@SHORT@',commit[:12]).replace('@RELEASE@',release)
    assert '@COMMIT@' not in spec
    (dest/'SPECS/mesa.spec').write_text(spec)
    clarification=gzip.decompress((recipe/'Mesa-MLAA-License-Clarification-Email.txt.gz').read_bytes())
    assert hashlib.sha256(clarification).hexdigest()=='68e7be52203a4457ea97d9c4744661a07fc3d78edb44a86b43349fb66f09147a'
    (dest/'SOURCES/Mesa-MLAA-License-Clarification-Email.txt').write_bytes(clarification)
    for item in json.loads((recipe/'sources.json').read_text()):
        fetch(item['url'],dest/'SOURCES'/item['file'],item['sha256'])
else:
    archive.rename(dest/'SOURCES'/('mesa-aurora-fex-guest-'+commit+'.tar.gz'))
    package=repo/'packages/mesa-aurora-fex-guest'
    for name in ('mesa-aurora-fex-guest.spec','aurora-fex-mesa.service','80-aurora-fex-mesa.preset'):
        shutil.copy(package/name,dest/('SPECS' if name.endswith('.spec') else 'SOURCES'))
manifest={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest()
          for directory in ('SOURCES','SPECS') for p in sorted((dest/directory).iterdir()) if p.is_file()}
(dest/'out/source-manifest.json').write_text(json.dumps({'commit':commit,'public_archive_sha256':checksum,
    'release':release,'kind':kind,'files':manifest},indent=2)+'\n')
