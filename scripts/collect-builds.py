#!/usr/bin/env python3
"""Download and authenticate exactly the RPM builds resolve-build-runs.py chose.

Each artifact must be the planned one (ID, run and digest), its run must
still qualify for the package under import-rpm-build.py's rules, and builds
whose workflow records provenance must carry a valid attestation for every
RPM. Accepted outputs land in --output as import-rpm-build.py lays them out.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts'))
import updatelib as lib  # noqa: E402

_spec = importlib.util.spec_from_file_location('importer', ROOT / 'scripts/import-rpm-build.py')
importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(importer)


def attests(commit):
    workflow = subprocess.run(['git', '-C', str(ROOT), 'show', f'{commit}:.github/workflows/rpms.yml'],
                              capture_output=True, text=True)
    return 'actions/attest-build-provenance' in workflow.stdout


def unpack(archive, destination):
    with zipfile.ZipFile(archive) as entries:
        if sum(entry.file_size for entry in entries.infolist()) > 4 * 1024**3:
            raise ValueError('expanded artifact exceeds its budget')
        for entry in entries.infolist():
            path = Path(entry.filename)
            mode = (entry.external_attr >> 16) & 0o170000
            if path.is_absolute() or '..' in path.parts or mode not in (0, 0o040000, 0o100000):
                raise ValueError('unsafe artifact entry')
        entries.extractall(destination)


def collect(plan, repository, output, downloads):
    if plan.get('schema') != 1 or plan.get('action') != 'publish':
        raise ValueError('the build plan is not publishable')
    if plan['head'] != lib.git(ROOT, 'rev-parse', 'HEAD'):
        raise ValueError('the build plan was resolved for another commit')
    builds = []
    for group in plan['runs']:
        run = str(group['run'])
        metadata = lib.gh_api(f'repos/{repository}/actions/runs/{run}')
        (downloads / f'build-{run}.json').write_text(json.dumps(metadata))
        artifacts = downloads / run
        for name in group['packages']:
            item = plan['packages'][name]
            artifact = lib.gh_api(f'repos/{repository}/actions/artifacts/{item["artifact"]}')
            if (artifact.get('workflow_run', {}).get('id') != int(run) or artifact['name'] != 'rpm-' + name
                    or artifact['expired'] or artifact['digest'] != item['digest']):
                raise ValueError(f'{name}: artifact {item["artifact"]} is not the planned output of run {run}')
            archive = downloads / f'{artifact["id"]}.zip'
            with archive.open('wb') as stream:
                subprocess.run(['gh', 'api', f'repos/{repository}/actions/artifacts/{artifact["id"]}/zip'],
                               stdout=stream, check=True)
            if 'sha256:' + lib.sha256_file(archive) != artifact['digest']:
                raise ValueError(f'{name}: artifact digest mismatch')
            unpack(archive, artifacts / ('rpm-' + name))
            archive.unlink()
            if attests(metadata['head_sha']):
                for rpm in sorted((artifacts / ('rpm-' + name) / 'out').glob('*rpms/*.rpm')):
                    subprocess.run(['gh', 'attestation', 'verify', str(rpm), '--repo', repository,
                                    '--signer-workflow', f'{repository}/.github/workflows/rpms.yml',
                                    '--source-digest', metadata['head_sha'], '--deny-self-hosted-runners'],
                                   check=True, stdout=subprocess.DEVNULL)
        count = importer.import_build(ROOT, metadata, artifacts, output, repository, matching_only=False,
                                      packages=set(group['packages']))
        if count != len(group['packages']):
            raise ValueError(f'run {run}: expected {len(group["packages"])} packages, imported {count}')
        shutil.rmtree(artifacts)
        builds.append(metadata)
    return builds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--downloads', type=Path, default=Path('downloaded'))
    args = parser.parse_args()
    if args.output.exists():
        parser.error('use a fresh output directory')
    args.downloads.mkdir(parents=True, exist_ok=True)
    builds = collect(json.loads(args.plan.read_text()), args.repository, args.output, args.downloads)
    print(f'Authenticated {sum(len(g["packages"]) for g in json.loads(args.plan.read_text())["runs"])} '
          f'package builds from {len(builds)} native run(s)')


if __name__ == '__main__':
    main()
