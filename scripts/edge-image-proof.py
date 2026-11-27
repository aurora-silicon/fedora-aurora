#!/usr/bin/env python3
"""Record what an Edge image carries: `edge-image-proof.json` schema 2.

aurora-distributions (scripts/edge_train.py) stages a payload only from an
image whose proof names the train's Edge snapshot, the Edge feed, the packaged
aurora-edge pair and the kernel and Mesa digests the hardware rows ran.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import edgelib  # noqa: E402

PROFILES = ('fedora-kde', 'fedora-gnome', 'fedora-minimal')
# Lab-only kernel arguments: never in an image that owners boot.
LAB_ONLY = ('systemd.debug_shell', 'panic', 'systemd.watchdog_sec', 'rd.break')


def kernel_arguments(root, kiwi=None):
    """The image's kernel command line: /etc/kernel/cmdline and every KIWI kernelcmdline."""
    arguments = []
    cmdline = root / 'etc/kernel/cmdline'
    if cmdline.is_file():
        arguments += cmdline.read_text().split()
    if kiwi is not None:
        import xml.etree.ElementTree as ET
        for node in ET.parse(kiwi).iter():
            arguments += node.get('kernelcmdline', '').split()
    return arguments


def refuse_lab_arguments(arguments):
    found = sorted({argument for argument in arguments if argument.split('=', 1)[0] in LAB_ONLY})
    if found:
        raise ValueError('the image carries lab-only kernel arguments: ' + ' '.join(found))


def file_digest(path):
    with path.open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def proof(root, profile, tag, sources, kiwi=None, fedora=44):
    root = Path(root).resolve(strict=True)
    if profile not in PROFILES:
        raise ValueError('not a Fedora profile: ' + profile)
    edgelib.snapshot(tag, fedora)
    refuse_lab_arguments(kernel_arguments(root, kiwi))
    repo = (root / 'etc/yum.repos.d/aurora.repo').read_text().splitlines()
    if ('baseurl=' + edgelib.REPOSITORY_URL) not in repo or 'enabled=1' not in repo:
        raise ValueError('the image does not follow the Edge feed')
    kernels = sorted(path for path in (root / 'usr/lib/modules').glob('*/vmlinuz') if path.is_file())
    if len(kernels) != 1:
        raise ValueError('an Edge image carries exactly one kernel')
    dso = root / 'usr/lib64/libvulkan_asahi.so'
    for path in (kernels[0], dso):
        if not path.resolve(strict=True).is_relative_to(root):
            raise ValueError('image member escapes its filesystem: ' + str(path))
    if set(sources) != {'linux', 'mesa'} or not all(
            re.fullmatch(r'[0-9a-f]{40}', sources[name].get(key, '')) for name in sources
            for key in ('revision', 'tree')):
        raise ValueError('invalid packaged sources')
    return {'schema': 2, 'distribution': 'fedora', 'profile': profile, 'channel': 'edge',
            'snapshot': tag, 'feed': edgelib.REPOSITORY_URL.replace('$releasever', str(fedora)),
            'packaged_sources': sources,
            'files': {'kernelImageSHA256': file_digest(kernels[0]), 'mesaDsoSHA256': file_digest(dso)}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--fedora-release', type=int, choices=(44, 45), default=44)
    parser.add_argument('--edge-sources', type=Path, required=True, help="the snapshot's edge-sources.json")
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kiwi-description', type=Path, help="the image description's config.xml")
    args = parser.parse_args()
    record = json.loads(args.edge_sources.read_text())
    if record.get('channel') != 'edge' or record.get('schema') != 1:
        parser.error('not an Edge snapshot record')
    args.output.write_text(json.dumps(proof(args.root, args.profile, args.snapshot, record['packaged_sources'],
                                            args.kiwi_description, args.fedora_release),
                                      indent=2, sort_keys=True) + '\n')
