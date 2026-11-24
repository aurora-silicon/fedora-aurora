"""The Edge channel: one aurora-edge Linux and Mesa pair over a Testing snapshot.

Kept out of fedoralib.SHARED: Edge publication is not RPM build tooling.
"""
import re

FEDORA = 44
FEED = 'https://aurorasilicon.org/fedora-aurora/44/edge/aarch64'
REPOSITORY_URL = 'https://aurorasilicon.org/fedora-aurora/$releasever/edge/aarch64'
TAG = re.compile(r'edge-(?:f45-)?[0-9]{8}\.[1-9][0-9]*')
REVISION = re.compile(r'[0-9a-f]{40}')
SOURCE_BRANCHES = {'linux': 'main', 'mesa': 'aurora-wip'}
# Packages an Edge build replaces, by family; every member of a family has one version.
FAMILIES = {'kernel': ('kernel-aurora', 'aurora-userpages'),
            'mesa': ('mesa-aurora', 'aurora-flatpak-gl')}
TRAIN_RECORD = 'site/installer/edge-train.json'


def snapshot(tag, fedora=44):
    if (int(fedora) not in (44, 45) or not isinstance(tag, str) or not TAG.fullmatch(tag)
            or tag.startswith('edge-f45-') != (int(fedora) == 45)):
        raise ValueError('Invalid immutable Fedora %s Edge snapshot tag: %r' % (fedora, tag))
    return tag


def family(name):
    for key, prefixes in FAMILIES.items():
        if any(name == prefix or name.startswith(prefix + '-') for prefix in prefixes):
            return key
    return None


def source(name, revision, tree):
    if not REVISION.fullmatch(revision or '') or not REVISION.fullmatch(tree or ''):
        raise ValueError('invalid %s revision or tree' % name)
    return {'repository': 'aurora-silicon/' + name, 'branch': SOURCE_BRANCHES[name],
            'revision': revision, 'tree': tree}
