#!/usr/bin/env python3
"""Reject stamp-only or incomplete GL exports before they become RPM payloads."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import tempfile

ID = 'org.freedesktop.Platform.GL.aurora'


def validate_payload(root, commit):
    root = Path(root).resolve()
    if (root / '.aurora-mesa-commit').read_text().strip() != commit:
        raise ValueError('GL payload has the wrong Mesa commit')
    for name in ('lib/libvulkan_asahi.so', 'lib/libvulkan_lvp.so',
                 'lib/libEGL_mesa.so.0', 'lib/libGLX_mesa.so.0',
                 'lib/libLLVM.so.22.1', 'lib/dri/aurora_dri.so',
                 'lib/dri/asahi_dri.so', 'lib/dri/zink_dri.so', 'lib/dri/swrast_dri.so'):
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError(f'{name}: symlink escapes the payload')
        with path.open('rb') as stream:
            header = stream.read(20)
        if header[:6] != b'\x7fELF\x02\x01' or struct.unpack('<H', header[18:20])[0] != 183:
            raise ValueError(f'{name}: not an AArch64 ELF library')
    for name in ('vulkan/icd.d/asahi_icd.aarch64.json',
                 'vulkan/icd.d/lvp_icd.aarch64.json',
                 'glvnd/egl_vendor.d/50_mesa.json'):
        data = json.loads((root / name).read_text())['ICD']
        library = data['library_path'].removeprefix('/usr/lib/aarch64-linux-gnu/GL/aurora/')
        # The loader can also use the basename with the extension's library path.
        path = root / (library if '/' in library else 'lib/' + library)
        if not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError(f'{name}: library_path is absent from the payload')
    defaults = (root / 'share/drirc.d/00-hk-defaults.conf').read_text()
    if 'hk_report_honeykrisp_driver_id' not in defaults:
        raise ValueError('GL payload lacks the DXVK/vkd3d driver-ID defaults')
    blob = (root / 'lib/libvulkan_asahi.so').read_bytes()
    expected = f'(git-{commit[:10]}), Borealis'.encode()
    if expected not in blob:
        raise ValueError('GL driverInfo lacks the pinned commit and Borealis name')


def validate_repo(repo, commit, branches):
    repo = Path(repo).resolve()
    for branch in branches:
        if (repo / f'aurora-mesa-commit.{branch}').read_text().strip() != commit:
            raise ValueError(f'{branch}: wrong repository Mesa stamp')
        ref = f'runtime/{ID}/aarch64/{branch}'
        with tempfile.TemporaryDirectory(prefix='aurora-gl-check-') as tmp:
            tree = Path(tmp) / 'tree'
            subprocess.run(['ostree', f'--repo={repo}', 'checkout', '--user-mode', ref, str(tree)], check=True)
            metadata = (tree / 'metadata').read_text()
            if '[ExtensionOf]' not in metadata or 'priority=10' not in metadata:
                raise ValueError(f'{branch}: missing GL extension metadata/priority')
            validate_payload(tree / 'files', commit)
        print(f'{ref}: complete AArch64 GL payload, Mesa {commit}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path')
    parser.add_argument('commit')
    parser.add_argument('branches', nargs='*')
    parser.add_argument('--payload', action='store_true')
    args = parser.parse_args()
    if args.payload:
        validate_payload(args.path, args.commit)
    else:
        if not args.branches:
            parser.error('at least one runtime branch is required')
        validate_repo(args.path, args.commit, args.branches)
