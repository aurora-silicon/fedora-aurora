#!/usr/bin/env python3
"""Refuse a package whose recipe would build an older EVR than the published Aurora repository has.

dnf never installs an older build over a newer one, so such a package would
silently never reach updated installs (as the Fedora 44 Plymouth 24.004 carry
nearly did over the published 26.134.222). For every Fedora release the
repository publishes, each source package in its primary metadata is compared
with the EVR packages/<name>/<name>.spec (or that release's overlay) builds.

    check-published-evr.py [--base URL] [--release 44 --release 45] [--channel testing]
"""
import argparse, gzip, io, lzma, re, subprocess, sys, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fedoralib  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NS = {'r': 'http://linux.duke.edu/metadata/repo', 'c': 'http://linux.duke.edu/metadata/common',
      'rpm': 'http://linux.duke.edu/metadata/rpm'}


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def decompress(data, name):
    if name.endswith('.gz'):
        return gzip.decompress(data)
    if name.endswith('.xz'):
        return lzma.decompress(data)
    if name.endswith('.zst'):
        return subprocess.run(['zstd', '-dc'], input=data, capture_output=True, check=True).stdout
    return data


def published(base):
    """{source name: (epoch, version, release)} of the newest source package in a repo."""
    repomd = ET.fromstring(fetch(base + '/repodata/repomd.xml'))
    href = next(d.find('r:location', NS).get('href') for d in repomd.findall('r:data', NS) if d.get('type') == 'primary')
    primary = ET.fromstring(decompress(fetch(base + '/' + href), href))
    newest = {}
    for pkg in primary.findall('c:package', NS):
        srpm = pkg.find('c:format/rpm:sourcerpm', NS)
        if srpm is None or not srpm.text:
            continue
        m = re.fullmatch(r'(.+)-([^-]+)-([^-]+)\.src\.rpm', srpm.text)
        if not m:
            continue
        name, ver, rel = m.groups()
        epoch = pkg.find('c:version', NS).get('epoch') or '0'
        evr = (epoch, ver, rel)
        if name not in newest or vercmp_evr(evr, newest[name]) > 0:
            newest[name] = evr
    return newest


def rpmvercmp(a, b):
    """rpm's version segment comparison, including ~ (sorts first) and ^ (sorts after the base)."""
    if a == b:
        return 0
    i = j = 0
    while i < len(a) or j < len(b):
        while i < len(a) and not (a[i].isalnum() or a[i] in '~^'):
            i += 1
        while j < len(b) and not (b[j].isalnum() or b[j] in '~^'):
            j += 1
        if (i < len(a) and a[i] == '~') or (j < len(b) and b[j] == '~'):
            if i >= len(a) or a[i] != '~':
                return 1
            if j >= len(b) or b[j] != '~':
                return -1
            i, j = i + 1, j + 1
            continue
        if (i < len(a) and a[i] == '^') or (j < len(b) and b[j] == '^'):
            if i >= len(a):
                return -1
            if j >= len(b):
                return 1
            if a[i] != '^':
                return 1
            if b[j] != '^':
                return -1
            i, j = i + 1, j + 1
            continue
        if i >= len(a) or j >= len(b):
            break
        num = a[i].isdigit()
        si, sj = i, j
        while i < len(a) and (a[i].isdigit() if num else a[i].isalpha()):
            i += 1
        while j < len(b) and (b[j].isdigit() if num else b[j].isalpha()):
            j += 1
        sa, sb = a[si:i], b[sj:j]
        if not sb:
            return 1 if num else -1
        if num:
            sa, sb = sa.lstrip('0'), sb.lstrip('0')
            if len(sa) != len(sb):
                return 1 if len(sa) > len(sb) else -1
        if sa != sb:
            return 1 if sa > sb else -1
    if i >= len(a) and j >= len(b):
        return 0
    return -1 if i >= len(a) else 1


def vercmp_evr(x, y):
    if int(x[0] or 0) != int(y[0] or 0):
        return 1 if int(x[0] or 0) > int(y[0] or 0) else -1
    return rpmvercmp(x[1], y[1]) or rpmvercmp(x[2], y[2])


def spec_evr(spec, release):
    """EVR the recipe builds for Fedora RELEASE, with rpmspec when available."""
    try:
        out = subprocess.run(['rpmspec', '-q', '--srpm', '--qf', '%{epochnum} %{version} %{release}\n',
                              '--define', f'fedora {release}', '--define', f'dist .fc{release}', str(spec)],
                             capture_output=True, text=True, check=True).stdout.split()
        return tuple(out[:3])
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    # Fallback: resolve %if 0%{?fedora} OP N blocks and %global macros.
    keep, stack, lines = True, [], []
    for line in spec.read_text().splitlines():
        m = re.match(r'%if\s+0%\{\?fedora\}\s*(==|!=|>=|<=|>|<)\s*(\d+)\s*$', line)
        if m:
            stack.append(keep)
            keep = keep and eval(f'{release} {m.group(1)} {m.group(2)}')
            continue
        if line.startswith('%if'):
            stack.append(keep)
            keep = keep and 'rhel' not in line
            continue
        if line.startswith('%else') and stack:
            keep = stack[-1] and not keep
            continue
        if line.startswith('%endif') and stack:
            keep = stack.pop()
            continue
        if keep:
            lines.append(line)
    text = '\n'.join(lines)
    macros = dict(re.findall(r'^%(?:global|define)\s+(\w+)\s+(\S+)', text, re.M))
    macros['dist'] = f'.fc{release}'
    def field(name):
        m = re.search(rf'^{name}:\s*(\S+)', text, re.M)
        value = m.group(1) if m else ''
        for _ in range(5):
            value = re.sub(r'%\{\??(\w+)\}', lambda x: macros.get(x.group(1), ''), value)
        return value
    return (field('Epoch') or '0', field('Version'), field('Release'))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base', default='https://aurorasilicon.org/fedora-aurora')
    parser.add_argument('--release', action='append', default=None)
    parser.add_argument('--channel', default='testing')
    args = parser.parse_args()
    failures = []
    for release in args.release or ['44', '45']:
        # A release's overlay (packages/<name>/f45/<name>.spec) replaces the base recipe.
        specs = {}
        for name in fedoralib.package_names(ROOT):
            spec = fedoralib.recipe_files(ROOT, name, release)[name + '.spec']
            m = re.search(r'^Name:\s*(\S+)', spec.read_text(), re.M)
            if m:
                specs[m.group(1)] = spec
        url = f'{args.base}/{release}/{args.channel}/aarch64'
        try:
            repo = published(url)
        except OSError as error:
            print(f'skip Fedora {release}: {url} not readable ({error})')
            continue
        for name, evr in sorted(repo.items()):
            if name not in specs:
                continue
            ours = spec_evr(specs[name], release)
            if not ours[1] or not ours[2] or '%' in ''.join(ours):
                # Version taken from another package at build time (for example
                # mesa-aurora's); that package is checked itself.
                print(f'skip Fedora {release} {name}: EVR is set at build time')
                continue
            if vercmp_evr(ours, evr) < 0:
                failures.append(f'Fedora {release} {name}: recipe builds {":".join(ours)}, published {":".join(evr)}')
    for line in failures:
        print('FAIL', line)
    print('published EVR check:', 'FAIL' if failures else 'PASS')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
