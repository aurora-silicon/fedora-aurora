#!/usr/bin/env python3
"""Assemble the Fedora DNF metadata site for every channel and record state.

GitHub Pages serves one site per repository, so every deployment publishes all
channels: 44/testing/aarch64, 44/stable/aarch64, 45/testing/aarch64 and 45/stable/aarch64.
Each holds the exact
signed metadata of an immutable snapshot release (its RPMs stay at the
release's URLs). A channel is the same signed bytes at another path, so
promotion never re-signs anything. `assemble` authenticates the snapshots and
writes the next channel state; `record` commits it after Pages accepted the
site.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts'))
import updatelib as lib  # noqa: E402
import fedoralib  # noqa: E402

CHANNELS = ('testing', 'stable')
SITE_BUDGET = 200_000_000
SLOTS = {'testing': (44, 'testing'), 'stable': (44, 'stable'),
         '45/testing': (45, 'testing'), '45/stable': (45, 'stable')}


def channel_key(channel, fedora=44):
    fedora = fedoralib.release(fedora)
    if channel not in CHANNELS:
        raise ValueError('unknown channel')
    return channel if fedora == 44 else f'{fedora}/{channel}'


def keyring(home):
    home.parent.mkdir(parents=True, exist_ok=True)
    home.mkdir(mode=0o700, exist_ok=True)
    subprocess.run(['gpg', '--homedir', str(home), '--batch', '--import', str(ROOT / 'keys/RPM-GPG-KEY-aurora')],
                   check=True, capture_output=True)
    listing = subprocess.check_output(['gpg', '--homedir', str(home), '--batch', '--with-colons', '--list-keys'],
                                      text=True)
    fingerprint = (ROOT / 'keys/fingerprint.txt').read_text().strip()
    if fingerprint not in [line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:')]:
        raise ValueError('keys/RPM-GPG-KEY-aurora does not hold the recorded fingerprint')
    return home, fingerprint


def gpg_verify(home, signature, data):
    subprocess.run(['gpg', '--homedir', str(home), '--batch', '--verify', str(signature), str(data)],
                   check=True, capture_output=True)


def verify_attestation(directory, repository):
    sums = directory / 'SHA256SUMS'
    if not sums.exists():
        return 'none (snapshot predates attestations)'
    listed = dict(reversed(line.split(maxsplit=1)) for line in sums.read_text().splitlines())
    listed = {name.lstrip('*'): digest for name, digest in listed.items()}
    archive = next(name for name in listed if name.startswith('repository-metadata-') and name.endswith('.tar.gz'))
    if listed[archive] != lib.sha256_file(directory / archive):
        raise ValueError('SHA256SUMS does not match the metadata archive')
    result = subprocess.run(['gh', 'attestation', 'verify', str(directory / archive), '--repo', repository,
                             '--signer-workflow', f'{repository}/.github/workflows/publish.yml',
                             '--deny-self-hosted-runners', '--format', 'json'],
                            check=True, capture_output=True, text=True)
    subjects = {(s['name'], s['digest']['sha256']) for v in json.loads(result.stdout)
                for s in v['verificationResult']['statement']['subject']}
    if not set(listed.items()) <= subjects:
        raise ValueError('the provenance attestation does not cover every snapshot asset')
    return 'verified'


def fetch_snapshot(repository, tag, channel, site, work, home, fingerprint, fedora=44):
    """Place the snapshot's signed metadata at <fedora>/<channel>/aarch64."""
    channel_key(channel, fedora)
    fedoralib.snapshot(tag, fedora)
    download = work / f'{fedora}-{channel}-download'
    download.mkdir(parents=True)
    lib.gh('release', 'download', tag, '--repo', repository, '--dir', str(download),
           '--pattern', 'repository-metadata-*', '--pattern', 'SHA256SUMS', '--pattern', 'manifest.json')
    archive = download / f'repository-metadata-{tag}.tar.gz'
    gpg_verify(home, archive.with_name(archive.name + '.asc'), archive)
    provenance = verify_attestation(download, repository)
    extracted = work / f'{fedora}-{channel}-metadata'
    with tarfile.open(archive) as bundle:
        bundle.extractall(extracted, filter='data')
    source = extracted / f'{fedora}/testing/aarch64'
    gpg_verify(home, source / 'repodata/repomd.xml.asc', source / 'repodata/repomd.xml')
    manifest = json.loads((source / 'manifest.json').read_text())
    if (manifest.get('dry_run') or manifest.get('signing_key') != fingerprint
            or manifest.get('fedora') != fedora or manifest.get('channel') != 'testing'
            or manifest.get('architecture') != 'aarch64'):
        raise ValueError(f'{tag}: metadata is not signed by the release key')
    if not manifest.get('asset_base', '').endswith('/' + tag):
        raise ValueError(f'{tag}: metadata points at another release')
    target = site / str(fedora) / channel / 'aarch64'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return provenance


def live_repository(site_url, channel, work, home, fedora=44):
    base = f'{site_url.rstrip("/")}/{fedora}/{channel}/aarch64'
    target = work / f'live-{fedora}-{channel}'
    try:
        lib.download([base + '/repodata/repomd.xml'], target / 'repodata/repomd.xml', attempts=3)
        lib.download([base + '/repodata/repomd.xml.asc'], target / 'repodata/repomd.xml.asc', attempts=3)
    except RuntimeError as error:
        if 'HTTP 404' in str(error):
            return None
        raise
    gpg_verify(home, target / 'repodata/repomd.xml.asc', target / 'repodata/repomd.xml')
    import xml.etree.ElementTree as ET
    ns = '{http://linux.duke.edu/metadata/repo}'
    for data in ET.parse(target / 'repodata/repomd.xml').getroot().findall(f'{ns}data'):
        if data.get('type') == 'primary':
            href = data.find(f'{ns}location').get('href')
            lib.download([f'{base}/{href}'], target / href, sha256=data.find(f'{ns}checksum').text, attempts=3)
    return target


def assemble(args):
    repository = args.repository
    key = channel_key(args.channel, args.fedora_release)
    state = lib.load_channels(ROOT, repository)
    current = {channel: state['channels'].get(channel, {}).get('tag') for channel in SLOTS}
    tag = args.tag
    if args.channel == 'stable':
        # Promote what the same release's testing channel served.
        testing = channel_key('testing', args.fedora_release)
        tag = tag or current[testing]
        if not tag:
            raise SystemExit('Nothing is on testing to promote.')
        served = lib.served_on(state, testing, 'tag', tag)
        if not served:
            raise SystemExit(f'{tag} has never been served on testing; promote only what testing users had.')
        first = min(item['deployed_at'] for item in served)
        soaked = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.datetime.fromisoformat(first.replace('Z', '+00:00'))).total_seconds() / 3600
        if soaked < args.min_soak_hours:
            raise SystemExit(f'{tag} has been on testing for {soaked:.1f} h; the minimum is {args.min_soak_hours} h.')
    if not tag:
        raise SystemExit('A release tag is required for the testing channel.')
    fedoralib.snapshot(tag, args.fedora_release)
    target = dict(current, **{key: tag})
    site, work = Path(args.site), Path(args.work)
    if site.exists():
        raise SystemExit('use a new site directory')
    home, fingerprint = keyring(work / 'gnupg')
    provenance = {}
    for slot, (fedora, channel) in SLOTS.items():
        if target[slot]:
            provenance[slot] = fetch_snapshot(repository, target[slot], channel, site, work, home, fingerprint, fedora)
    report = ''
    live = live_repository(args.site_url, args.channel, work, home, args.fedora_release)
    if live is not None:
        command = [sys.executable, str(ROOT / 'scripts/check-feed-versions.py'), '--old', str(live),
                   '--new', str(site / str(args.fedora_release) / args.channel / 'aarch64')]
        if args.allow_downgrade:
            command.append('--allow-downgrade')
        checked = subprocess.run(command, capture_output=True, text=True)
        report = checked.stdout + checked.stderr
        if checked.returncode:
            print(report, file=sys.stderr)
            raise SystemExit('The new snapshot would downgrade packages on this channel.')
    shutil.copyfile(ROOT / 'keys/RPM-GPG-KEY-aurora', site / 'RPM-GPG-KEY-aurora')
    shutil.copyfile(ROOT / 'keys/fingerprint.txt', site / 'fingerprint.txt')
    total = sum(path.stat().st_size for path in site.rglob('*') if path.is_file())
    if total >= SITE_BUDGET:
        raise SystemExit(f'site is {total} bytes; metadata should be far smaller')
    release = lib.gh_api(f'repos/{repository}/releases/tags/{tag}')
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    entry = {'tag': tag, 'commit': release['target_commitish'], 'released_at': release['created_at'],
             'deployed_at': now, 'run_id': os.environ.get('GITHUB_RUN_ID', ''),
             'actor': os.environ.get('GITHUB_ACTOR', ''), 'provenance': provenance[key]}
    new_state = lib.record_channel(state, key, entry)
    (site / 'channels.json').write_text(json.dumps({'repository': repository, 'channels': new_state['channels'],
                                                    'updated_at': now}, indent=2, sort_keys=True) + '\n')
    items = ''.join(f'<li>{c}: <code>baseurl=https://aurorasilicon.org/fedora-aurora/{SLOTS[c][0]}/{SLOTS[c][1]}/aarch64</code> '
                    f'({target[c]})</li>' for c in SLOTS if target[c])
    (site / 'index.html').write_text(f'<!doctype html><title>Aurora Fedora Remix</title>'
                                     f'<h1>Aurora Fedora Remix RPM repositories</h1><ul>{items}</ul>\n')
    Path(args.state_out).write_text(json.dumps(new_state, indent=2) + '\n')
    lines = [f'## {key}: {current[key] or "(none)"} -> {tag}', '']
    lines += [f'- {c}: `{target[c]}` (attestation: {provenance[c]})' for c in SLOTS if target[c]]
    lines += ['', '```', report.strip() or 'no live repository to compare', '```']
    print('\n'.join(lines))


def record(args):
    state = json.loads(Path(args.state).read_text())
    if state.get('repository') != args.repository:
        raise SystemExit('state belongs to another repository')
    key = channel_key(args.channel, args.fedora_release)
    entry = state['channels'][key]
    lib.commit_channels(ROOT, state, f'Serve {entry["tag"]} on {key}\n\nRun {entry.get("run_id", "")}')
    print(f'Recorded {entry["tag"]} on {key}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY', ''))
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('assemble')
    build.add_argument('--fedora-release', type=int, choices=fedoralib.RELEASES, default=44)
    build.add_argument('--channel', choices=CHANNELS, required=True)
    build.add_argument('--tag', default='')
    build.add_argument('--allow-downgrade', action='store_true')
    build.add_argument('--min-soak-hours', type=float, default=0.0)
    build.add_argument('--site', required=True)
    build.add_argument('--work', required=True)
    build.add_argument('--state-out', required=True)
    build.add_argument('--site-url', default='https://aurorasilicon.org/fedora-aurora')
    store = commands.add_parser('record')
    store.add_argument('--fedora-release', type=int, choices=fedoralib.RELEASES, default=44)
    store.add_argument('--channel', choices=CHANNELS, required=True)
    store.add_argument('--state', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
        parser.error('--repository owner/name is required')
    assemble(args) if args.command == 'assemble' else record(args)


if __name__ == '__main__':
    main()
