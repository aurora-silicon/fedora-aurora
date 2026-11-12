#!/usr/bin/env python3
"""Import Fedora's Firefox recipe into packages/firefox with Aurora's changes.

The recipe is Fedora's dist-git tree for the release branch, byte for byte,
except:

- firefox.spec gets the edits in `edit_spec` (the RDD V4L2 Request patch, an
  Aurora release suffix, and the build switches that fit the native builder);
- the API key files are not copied: they are Fedora's, so the build fetches
  them from the same dist-git commit (distgit.json pins their SHA-256);
- `sources` (Fedora's lookaside list) is kept, and the build fetches those
  archives from Fedora's lookaside cache by their SHA-512.

Fedora 44 is the base directory; a Fedora 45 file that differs goes to f45/.
Run with no arguments to import the current branch heads, or give checkouts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages' / 'firefox'
REPOSITORY = 'https://src.fedoraproject.org/rpms/firefox.git'
RELEASES = {44: 'f44', 45: 'f45'}
FETCHED = ('google-api-key', 'google-loc-api-key', 'mozilla-api-key')
OURS = ('rdd-v4l2-request.patch',)
SKIP = {'.git', '.gitignore', 'sources'} | set(FETCHED)
AURORA_RELEASE = '.aurora2'
CHANGELOG = """\
* {date} Aurora Silicon <hey@djdev.me> - {evr}
- Rebuild of Fedora's firefox-{version}-{release}.
- Allow V4L2 stateless (Request API) decoders in the RDD sandbox.
- Allow sysinfo in the RDD sandbox, so Mesa's zink driver can create the
  GBM device behind VA-API DMABuf surfaces.
- No debuginfo, no Rust debug info and no WASI SDK build, to fit the native
  builder.

"""


def git(*args, cwd=None):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def once(text, pattern, replacement, what):
    new, count = re.subn(pattern, replacement, text, count=1, flags=re.M)
    if count != 1 or len(re.findall(pattern, text, flags=re.M)) != 1:
        raise SystemExit(f'firefox.spec: {what}: expected exactly one match for {pattern!r}')
    return new


def edit_spec(text, commit, date):
    version = re.search(r'^Version:\s+(\S+)$', text, re.M)[1]
    release = re.search(r'^Release:\s+(\S+)$', text, re.M)[1]
    if not release.endswith('%{?dist}'):
        raise SystemExit(f'firefox.spec: unexpected Release {release}')
    text = ('# aurora-builder: heavy\n'
            '# Imported from Fedora dist-git by scripts/import-fedora-firefox.py; edit that\n'
            '# script, not this file.\n\n') + text
    text = once(text, r'^%global create_debuginfo  1$', '%global create_debuginfo  0', 'debuginfo')
    text = once(text, r'^  %bcond wasi_sdk 1$', '  %bcond wasi_sdk 0', 'WASI SDK')
    # With no debuginfo package, Rust debug info only costs memory: gkrust at
    # -Cdebuginfo=2 -Ccodegen-units=1 is killed by the OOM killer on the
    # 16 GB arm64 builder with Fedora 45's Rust.  Fedora already builds Rust
    # without debug info on its smaller architectures.
    text = once(text, r'^%ifarch %\{ix86\} s390x ppc64le\n(export RUSTFLAGS="-Cdebuginfo=0")$',
                r'%ifarch %{ix86} s390x ppc64le aarch64\n\g<1>', 'Rust debug info')
    text = once(text, r'^(Release:\s+\S+%\{\?dist\})$', r'\g<1>' + AURORA_RELEASE, 'Release')
    patches = list(re.finditer(r'^Patch\d+:.*$', text.split('\n%description', 1)[0], re.M))
    if not patches:
        raise SystemExit('firefox.spec: no Patch lines')
    end = patches[-1].end()
    text = (text[:end] + '\n\n# Aurora: V4L2 stateless decoders in RDD (Mozilla bug 2080696)\n'
            'Patch900:       rdd-v4l2-request.patch\nBuildRequires:  kernel-headers >= 6.5' + text[end:])
    text = once(text, r'^rm -f \.mozconfig$', '%patch -P900 -p1 -b .rdd-v4l2-request\n\nrm -f .mozconfig',
                'patch application')
    head, marker, history = text.partition('\n%changelog\n')
    if not marker:
        raise SystemExit('firefox.spec: no %changelog')
    entry = CHANGELOG.format(date=date, version=version, release=release.replace('%{?dist}', ''),
                             evr=f'{version}-{release.replace("%{?dist}", "")}{AURORA_RELEASE}')
    return head + marker + entry + history


def checkout(branch, work):
    target = work / branch
    subprocess.run(['git', 'clone', '-q', '--depth=1', '-b', branch, REPOSITORY, str(target)], check=True)
    return target


def files_of(tree, branch, commit, date):
    files = {}
    for path in sorted(tree.iterdir()):
        if path.name in SKIP or not path.is_file():
            if path.is_dir() and path.name != '.git':
                raise SystemExit(f'{tree}: unexpected directory {path.name}')
            continue
        data = path.read_bytes()
        if path.name == 'firefox.spec':
            data = edit_spec(data.decode(), commit, date).encode()
        files[path.name] = (data, path.stat().st_mode & 0o111 != 0)
    for name in FETCHED:
        if not (tree / name).is_file():
            raise SystemExit(f'{tree}: {name} is missing')
    files['distgit.json'] = ((json.dumps({
        'repository': REPOSITORY, 'branch': branch,
        'commit': commit,
        'fetch': {name: hashlib.sha256((tree / name).read_bytes()).hexdigest() for name in FETCHED},
    }, indent=2) + '\n').encode(), False)
    files['sources'] = ((tree / 'sources').read_bytes(), False)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--f44', type=Path, help='Fedora 44 dist-git checkout (default: clone f44)')
    parser.add_argument('--f45', type=Path, help='Fedora 45 dist-git checkout (default: clone f45)')
    parser.add_argument('--date', help='changelog date, e.g. "Wed Nov 11 2026" (default: today)')
    parser.add_argument('--check', action='store_true', help='fail if packages/firefox differs instead of writing')
    args = parser.parse_args()
    date = args.date or subprocess.check_output(['date', '+%a %b %d %Y'], text=True).strip()
    with tempfile.TemporaryDirectory() as tmp:
        trees = {}
        for release, branch in RELEASES.items():
            given = getattr(args, branch)
            trees[release] = given.resolve() if given else checkout(branch, Path(tmp))
        commits = {release: git('rev-parse', 'HEAD', cwd=tree) for release, tree in trees.items()}
        if args.date is None and PACKAGE.joinpath('distgit.json').exists():
            # Re-importing the same commits keeps the recorded changelog date.
            old = json.loads(PACKAGE.joinpath('distgit.json').read_text())
            if old['commit'] == commits[44]:
                date = re.search(r'^\* (\w{3} \w{3} \d\d \d{4}) Aurora Silicon',
                                 PACKAGE.joinpath('firefox.spec').read_text(), re.M)[1]
        base = files_of(trees[44], 'f44', commits[44], date)
        f45 = files_of(trees[45], 'f45', commits[45], date)
        if set(base) - set(f45):
            raise SystemExit(f'f45 lacks {sorted(set(base) - set(f45))}; an overlay cannot remove a file')
        overlay = {name: data for name, data in f45.items() if base.get(name) != data}
    wanted = {name: data for name, data in base.items()}
    wanted.update({f'f45/{name}': data for name, data in overlay.items()})
    for name in OURS:
        wanted[name] = ((PACKAGE / name).read_bytes(), False)
    # Content and the executable bit: the spec copies helper scripts and runs them.
    present = {p.relative_to(PACKAGE).as_posix(): (p.read_bytes(), p.stat().st_mode & 0o111 != 0)
               for p in PACKAGE.rglob('*') if p.is_file()} if PACKAGE.exists() else {}
    if args.check:
        if present != wanted:
            changed = sorted(set(present) ^ set(wanted) | {n for n in present.keys() & wanted.keys()
                                                         if present[n] != wanted[n]})
            raise SystemExit('packages/firefox is not the import of Fedora dist-git: ' + ', '.join(changed))
        print(f'packages/firefox matches f44 {commits[44][:12]} / f45 {commits[45][:12]}')
        return
    for name in set(present) - set(wanted):
        (PACKAGE / name).unlink()
    for name, (data, executable) in wanted.items():
        target = PACKAGE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if present.get(name) != (data, executable):
            target.write_bytes(data)
            target.chmod(0o755 if executable else 0o644)
    if (PACKAGE / 'f45').is_dir() and not any((PACKAGE / 'f45').iterdir()):
        (PACKAGE / 'f45').rmdir()
    version = re.search(r'^Version:\s+(\S+)$', base['firefox.spec'][0].decode(), re.M)[1]
    print(f'Imported Firefox {version}: f44 {commits[44][:12]}, f45 {commits[45][:12]}'
          f'{" (overlay: " + ", ".join(sorted(overlay)) + ")" if overlay else ""}')


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    main()
