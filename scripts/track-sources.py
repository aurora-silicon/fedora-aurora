#!/usr/bin/env python3
"""Propose Fedora RPM spec updates for tracked upstream branches.

`plan` is read-only with respect to GitHub: it writes a patch and a result
record under --output. `open-pr`, `merge` and `mirror` act on GitHub with the
workflow token. See docs/updates.md.
"""
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import trackerlib as tl  # noqa: E402
import updatelib as lib  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RECIPES = {'kernel-aurora': 'kernel-aurora', 'aura': 'aura', 'mesa-aurora': 'mesa-aurora'}
KINDS = {'kernel-aurora': 'kernel', 'mesa-aurora': 'mesa'}
CI_WORKFLOWS = ['rpms.yml', 'checks.yml']
# The only files a tracker proposal may change.
PATCH_PATHS = [r'sources\.json', r'packages/(kernel-aurora|aura|mesa-aurora)/[^/]+\.spec']


def update_recipe(root, item, today):
    """Apply one source update to its spec. Returns review notes."""
    key = item['key']
    spec = root / 'packages' / RECIPES[key] / f'{RECIPES[key]}.spec'
    original = spec.read_text()
    previous = (tl.spec_field(original, 'Version'), tl.spec_field(original, 'Release').split('%')[0])
    text = tl.replace_commit(original, item['old'], item['new'])
    if not re.search(rf'^%global commit {item["new"]}$', text, re.M):
        raise ValueError(f'{key}: the spec does not pin %global commit to the new commit')
    notes = []
    old_version = tl.spec_field(text, 'Version')
    new_version = tl.rpm_version(item['version']) if item.get('version') else old_version
    if new_version != old_version:
        text = tl.set_spec_field(text, 'Version', new_version)
        notes.append(f'Version {old_version} -> {new_version}: review the spec and configuration')
    text, release = tl.bump_spec_release(text, reset=new_version != old_version)
    setup = re.search(r'^%autosetup\b.*?-n\s+(\S+)', text, re.M)
    if setup and setup[1].replace('%{commit}', item['new']) != item.get('archive_root', setup[1]):
        notes.append(f'%autosetup -n {setup[1]} does not name the archive root {item["archive_root"]}')
        item.setdefault('needs_review', []).append('the spec unpacks a different directory than the archive holds')
    lines = [f'Track {item["repository"]} {item["branch"]} at {item["new"][:7]}.']
    if item.get('new_subject'):
        lines.append(f'Upstream head: {item["new_subject"]}')
    text = tl.add_spec_changelog(text, new_version, release, lines, today)
    spec.write_text(text)
    dist = tl.spec_field(text, 'Release')
    item['package_version'] = f'{new_version}-{dist.replace("%{?dist}", ".fc44")}'
    if lib.rpm_evr_compare(('0', new_version, str(release)), ('0', *previous)) <= 0:
        raise ValueError(f'{key}: {new_version}-{release} would not upgrade {"-".join(previous)}')
    return notes


def run_checks(root):
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'],
                   cwd=root, check=True)
    subprocess.run([sys.executable, 'images/test_configure.py'], cwd=root, check=True)


def ci_inputs(packages):
    return {'rpms.yml': {'packages': ' '.join(packages)}}


if __name__ == '__main__':
    tl.main(sys.modules[__name__])
