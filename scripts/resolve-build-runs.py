#!/usr/bin/env python3
"""Choose, for every Fedora package, the newest native build that may be published.

A build qualifies under import-rpm-build.py's rules: a successful push or
manual rpms.yml run whose commit is merged, with the package recipe, its
source pin and the shared build tooling unchanged since. The newest
qualifying run with an unexpired artifact wins for each package. Packages
without one are carried from the base snapshot by assemble-repository.py,
which still requires the current spec's exact source NVR. Nothing is
downloaded here.

`action` is `publish` when some chosen build is not in any published
snapshot yet, otherwise `up-to-date`.
"""
import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts'))
import updatelib as lib  # noqa: E402

_spec = importlib.util.spec_from_file_location('importer', ROOT / 'scripts/import-rpm-build.py')
importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(importer)

WORKFLOW = 'rpms.yml'
RETENTION_DAYS = 30


def packages(root):
    return sorted(path.parent.name for path in (root / 'packages').glob('*/*.spec')
                  if path.stem == path.parent.name)


def eligible_packages(root, run, repository):
    commit = run.get('head_sha', '')
    if (run.get('conclusion') != 'success' or run.get('head_repository', {}).get('full_name') != repository
            or run.get('event') not in ('push', 'workflow_dispatch')
            or run.get('path') != f'.github/workflows/{WORKFLOW}' or not lib.HEX40.fullmatch(commit)
            or not lib.is_ancestor(root, commit)):
        return set()
    for path in importer.SHARED:
        if lib.tree_id(root, commit, path) != lib.tree_id(root, 'HEAD', path):
            return set()
    try:
        previous = lib.json_at(root, commit, 'sources.json')
    except Exception:
        return set()
    current = json.loads((root / 'sources.json').read_text())
    return {name for name in packages(root)
            if lib.tree_id(root, commit, f'packages/{name}') == lib.tree_id(root, 'HEAD', f'packages/{name}')
            and previous.get(name) == current.get(name)}


def successful_runs(repository, now=None, api=lib.gh_api):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    oldest = now - datetime.timedelta(days=RETENTION_DAYS)
    runs = []
    for page in range(1, 6):
        batch = api(f'repos/{repository}/actions/workflows/{WORKFLOW}/runs?status=success&per_page=100'
                    f'&page={page}').get('workflow_runs', [])
        fresh = [run for run in batch
                 if datetime.datetime.fromisoformat(run['created_at'].replace('Z', '+00:00')) >= oldest]
        runs.extend(fresh)
        if len(batch) < 100 or len(fresh) < len(batch):
            break
    return sorted(runs, key=lambda run: (run['created_at'], run['id']), reverse=True)


def newest_artifacts(repository, run_id, api=lib.gh_api):
    pages = api(f'repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100', paginate=True)
    newest = {}
    for artifact in [item for page in pages for item in page['artifacts']]:
        if artifact['expired']:
            continue
        current = newest.get(artifact['name'])
        if current is None or (artifact['created_at'], artifact['id']) > (current['created_at'], current['id']):
            newest[artifact['name']] = artifact
    return newest


def published_runs(repository, limit=30):
    """Native build IDs that published snapshots already include."""
    releases = lib.gh_api(f'repos/{repository}/releases?per_page=100')
    snapshots = sorted((r for r in releases if r['tag_name'].startswith('testing-') and not r['draft']),
                       key=lambda r: r['created_at'], reverse=True)[:limit]
    found = set()
    for release in snapshots:
        asset = next((a for a in release['assets'] if a['name'] == 'builds.json'), None)
        if asset:
            data = json.loads(lib.gh('api', '-H', 'Accept: application/octet-stream',
                                     f'repos/{repository}/releases/assets/{asset["id"]}').stdout)
            found.update(int(build['id']) for build in data.get('builds', []))
    return found, (snapshots[0]['tag_name'] if snapshots else None)


def resolve(root, repository, runs, artifacts_for, published=frozenset(), base_release=None):
    wanted = packages(root)
    chosen = {}
    for run in runs:
        pending = [name for name in wanted if name not in chosen]
        if not pending:
            break
        names = eligible_packages(root, run, repository) & set(pending)
        if not names:
            continue
        artifacts = artifacts_for(run['id'])
        for name in sorted(names):
            artifact = artifacts.get('rpm-' + name)
            if artifact:
                chosen[name] = {'run': run['id'], 'head_sha': run['head_sha'], 'artifact': artifact['id'],
                                'digest': artifact['digest'], 'bytes': artifact['size_in_bytes']}
    carried = [name for name in wanted if name not in chosen]
    if all(item['run'] in published for item in chosen.values()):
        # Nothing newer than the published snapshots; with no snapshot at all
        # every package needs a build.
        action = 'up-to-date' if base_release else 'missing'
    elif carried and not base_release:
        action = 'missing'
    else:
        action = 'publish'
    groups = {}
    for name, item in chosen.items():
        groups.setdefault(item['run'], []).append(name)
    return {'schema': 1, 'action': action, 'head': lib.git(root, 'rev-parse', 'HEAD'),
            'base_release': base_release, 'packages': chosen, 'carried': carried,
            'runs': [{'run': run, 'packages': sorted(names)} for run, names in sorted(groups.items())],
            'rebuild': carried if action == 'missing' else []}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--base-release', help='snapshot supplying unchanged packages (default: newest testing-*)')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
        parser.error('--repository owner/name')
    published, newest = published_runs(args.repository)
    plan = resolve(ROOT, args.repository, successful_runs(args.repository),
                   lambda run_id: newest_artifacts(args.repository, run_id), published,
                   args.base_release or newest)
    args.output.write_text(json.dumps(plan, indent=2) + '\n')
    lib.write_github_output(action=plan['action'], base_release=plan['base_release'] or '',
                            rebuild=' '.join(plan['rebuild']))
    for name, item in sorted(plan['packages'].items()):
        print(f'{name}: run {item["run"]} ({item["head_sha"][:12]})')
    for name in plan['carried']:
        print(f'{name}: carried from {plan["base_release"]}')
    print(f'Action: {plan["action"]}')


if __name__ == '__main__':
    main()
