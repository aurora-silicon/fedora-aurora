#!/usr/bin/env python3
"""Carry the Fedora 45 RPMs of heavy recipes a full run did not build from the newest F45 snapshot.

rpms.yml leaves recipes marked "# aurora-builder: heavy" (Firefox, about three
hours) out of the implicit full set, but repository-fedora45 resolves the fleet
upgrade from the complete fc45 inventory. For every heavy recipe the run did
not build, the newest testing-f45-* snapshot supplies its signed binary RPMs.
The snapshot's build receipt for the recipe (builds.json, followed back
through base snapshots) must record exactly the current recipe inputs; a
snapshot carrying a build of an older recipe fails, so a stale build is never
taken for the current one. Build and publish the recipe, then run again.

    carry-heavy-f45.py --repository OWNER/NAME --candidates DIR --output DIR

OUTPUT gets the carried RPMs, manifest.json (the snapshot manifest restricted
to them, for assemble-repository.py --base) and carried.json (snapshot, receipt
and files per package). With nothing to carry, OUTPUT is not created.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts'))
import fedoralib  # noqa: E402

FEDORA = 45
HEAVY = '# aurora-builder: heavy'
# Base snapshots followed to find the build receipt of a carried package.
RECEIPT_DEPTH = 30


class StaleSnapshot(SystemExit):
    pass


def asset_name(filename):
    """The name GitHub stores a release asset under (assemble-repository.py)."""
    return re.sub(r'[^A-Za-z0-9._-]', '.', filename)


def heavy_names(root):
    names = []
    for name in fedoralib.package_names(root):
        spec = fedoralib.recipe_files(root, name, FEDORA)[name + '.spec']
        if HEAVY in spec.read_text().splitlines():
            names.append(name)
    return names


def built_names(candidates):
    return {receipt.stem for receipt in Path(candidates).glob('rpm-f45-*/out/manifests/*.json')
            if receipt.parents[2].name == fedoralib.artifact(receipt.stem, FEDORA)}


def snapshots(releases):
    """Published F45 snapshots by tag, and the newest tag."""
    found = {r['tag_name']: r for r in releases
             if r['tag_name'].startswith(fedoralib.prefix(FEDORA)) and not r.get('draft')}
    newest = max(found.values(), key=lambda r: (r['created_at'], r['id']))['tag_name'] if found else None
    return found, newest


def find_receipt(name, tag, found, read_json):
    """The newest F45 build receipt for NAME in TAG or the snapshots it was based on."""
    for _ in range(RECEIPT_DEPTH):
        release = found.get(tag)
        if release is None or not any(a['name'] == 'builds.json' for a in release['assets']):
            break
        builds = read_json(tag, 'builds.json')
        for receipt in builds.get('receipts', []):
            if receipt.get('package') == name and receipt.get('fedora', 44) == FEDORA:
                return tag, receipt
        base = builds.get('base_release')
        if not base:
            break
        tag = fedoralib.snapshot(base, FEDORA)
    raise StaleSnapshot(f'{name}: no Fedora 45 build receipt found from the newest snapshot back')


def carry(root, candidates, output, releases, read_json, download):
    """Plan and fetch the carried packages; returns carried.json's content or None."""
    missing = [name for name in heavy_names(root) if name not in built_names(candidates)]
    if not missing:
        return None
    found, newest = snapshots(releases)
    if newest is None:
        raise StaleSnapshot(f'No Fedora 45 snapshot can supply {", ".join(missing)}')
    manifest = read_json(newest, 'manifest.json')
    if manifest.get('fedora') != FEDORA or manifest.get('dry_run'):
        raise StaleSnapshot(f'{newest} is not a signed Fedora 45 snapshot')
    entries = {asset_name(row['filename']): row for row in manifest['packages']}
    output = Path(output)
    output.mkdir(parents=True)
    record = {'schema': 1, 'snapshot': newest, 'packages': {}}
    kept = []
    for name in missing:
        source, receipt = find_receipt(name, newest, found, read_json)
        if receipt.get('succeeded') is not True:
            raise StaleSnapshot(f'{name}: the receipt in {source} is not a successful build')
        current = fedoralib.recipe_inputs(root, name, FEDORA)
        if receipt.get('recipe_inputs') != current:
            changed = sorted(k for k in current.keys() | receipt.get('recipe_inputs', {}).keys()
                             if current.get(k) != receipt.get('recipe_inputs', {}).get(k))
            raise StaleSnapshot(
                f'{name}: {newest} carries a build of an older recipe (receipt in {source}; changed: '
                f'{", ".join(changed)}). Build {name} for Fedora 45 (rpms.yml with packages={name}) and '
                f'publish it, then run this job again.')
        binaries = sorted(row['filename'] for row in receipt.get('artifacts', [])
                          if not row['filename'].endswith(('.src.rpm', '.nosrc.rpm')))
        if not binaries:
            raise StaleSnapshot(f'{name}: the receipt in {source} lists no binary RPMs')
        files = []
        for filename in binaries:
            asset = asset_name(filename)
            entry = entries.get(asset)
            if entry is None:
                raise StaleSnapshot(f'{name}: {newest} does not carry {filename} from the build in {source}')
            path = download(newest, asset, output)
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if path.is_symlink() or path.stat().st_size != entry['bytes'] or digest != entry['sha256']:
                raise StaleSnapshot(f'{asset}: differs from the {newest} manifest')
            files.append({'filename': asset, 'sha256': entry['sha256'], 'bytes': entry['bytes']})
            kept.append(entry)
        record['packages'][name] = {'receipt_snapshot': source, 'recipe_inputs': current, 'files': files}
    (output / 'manifest.json').write_text(json.dumps({**manifest, 'packages': kept}, indent=2) + '\n')
    (output / 'carried.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
        parser.error('--repository owner/name')
    if args.output.exists():
        parser.error('output exists')
    import updatelib as lib
    releases = [r for page in lib.gh_api(f'repos/{args.repository}/releases?per_page=100', paginate=True)
                for r in page]
    scratch = args.output.with_name(args.output.name + '-metadata')

    def fetch(tag, name, directory):
        fedoralib.snapshot(tag, FEDORA)
        directory.mkdir(parents=True, exist_ok=True)
        lib.gh('release', 'download', tag, '--repo', args.repository, '--pattern', name,
               '--dir', str(directory), '--clobber')
        return directory / name

    def read_json(tag, name):
        return json.loads(fetch(tag, name, scratch / tag).read_text())

    try:
        record = carry(ROOT, args.candidates, args.output, releases, read_json, fetch)
    except StaleSnapshot as error:
        print(f'::error::{error}', file=sys.stderr)
        raise
    if record is None:
        print('Every heavy recipe was built in this run; nothing carried')
        return
    for name, item in record['packages'].items():
        print(f'{name}: carried from {record["snapshot"]} (receipt in {item["receipt_snapshot"]}, '
              f'recipe inputs match): {", ".join(f["filename"] for f in item["files"])}')


if __name__ == '__main__':
    main()
