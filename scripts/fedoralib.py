"""Release boundaries shared by builders, artifact import and publication."""
import hashlib
import json
from pathlib import Path
import re

RELEASES = (44, 45)


def release(value):
    value = int(value)
    if value not in RELEASES:
        raise ValueError('Only Fedora 44 and 45 are supported')
    return value


def prefix(fedora=44):
    return 'testing-' if release(fedora) == 44 else 'testing-f45-'


def snapshot(tag, fedora=44):
    if not re.fullmatch(re.escape(prefix(fedora)) + r'[A-Za-z0-9._-]+', tag):
        raise ValueError('Invalid immutable snapshot tag for this Fedora release')
    if release(fedora) == 44 and tag.startswith('testing-f45-'):
        raise ValueError('A Fedora 45 snapshot cannot supply Fedora 44')
    return tag


def artifact(name, fedora=44):
    # Preserve the existing Fedora 44 artifact contract, including old runs.
    return ('rpm-' if release(fedora) == 44 else 'rpm-f45-') + name


def package_names(root):
    return sorted(p.parent.name for p in (Path(root) / 'packages').glob('*/*.spec')
                  if p.stem == p.parent.name)


def recipe_files(root, name, fedora=44):
    fedora = release(fedora)
    directory = Path(root) / 'packages' / name
    files = {p.name: p for p in directory.iterdir() if p.is_file()}
    overlay = directory / f'f{release(fedora)}'
    if fedora != 44 and overlay.is_dir():
        files.update({p.name: p for p in overlay.iterdir() if p.is_file()})
    return files


def recipe_inputs(root, name, fedora=44):
    directory = Path(root) / 'packages' / name
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(recipe_files(root, name, fedora).values())}


def sources(root, fedora=44):
    fedora = release(fedora)
    pins = json.loads((Path(root) / 'sources.json').read_text())
    if release(fedora) != 44:
        for path in sorted((Path(root) / 'packages').glob(f'*/f{fedora}/sources.json')):
            pins.update(json.loads(path.read_text()))
    return pins
