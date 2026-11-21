#!/usr/bin/env python3
"""Assemble the RPM set of one Edge snapshot: a Testing snapshot with its kernel and Mesa
packages replaced by the signed Edge build of one aurora-edge pair.

The Edge RPMs are the exact bytes the Edge signer (edge-f44-sign-rpms.yml)
produced and the hardware rows ran; nothing is rebuilt. Writes the complete
RPM directory and `edge-sources.json`, the packaged Linux and Mesa records.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import edgelib  # noqa: E402


def identity(path):
    return subprocess.check_output(['rpm', '-qp', '--qf', '%{NAME}.%{ARCH}', str(path)], text=True).strip()


def version(key, filename):
    name, arch = key.rsplit('.', 1)
    suffix = '.' + arch + '.rpm'
    if not filename.startswith(name + '-') or not filename.endswith(suffix):
        raise ValueError('RPM file name differs from its identity: ' + filename)
    return filename[len(name) + 1:-len(suffix)]


def plan(base, edge, mesa=None, sources=False):
    """`base` and `edge` are (NAME.ARCH, file name) rows; `mesa`, when given, are the Mesa
    replacement signer's rows, which supply the whole Mesa family instead of `edge`.
    Returns the base files kept and the Edge files added (and, with `sources`, which
    signer artifact each added file comes from)."""
    origin = {}
    if mesa is not None:
        if any(edgelib.family(key.rsplit('.', 1)[0]) != 'mesa' for key, _ in mesa):
            raise ValueError('the Mesa replacement signer carries something that is not a Mesa package')
        edge = [row for row in edge if edgelib.family(row[0].rsplit('.', 1)[0]) != 'mesa']
        origin.update({filename: 'mesa' for _, filename in mesa})
        edge = edge + list(mesa)
    families = {}
    replaced = set()
    for key, filename in edge:
        kind = edgelib.family(key.rsplit('.', 1)[0])
        if kind is None:
            raise ValueError('not a kernel or Mesa package: ' + filename)
        if key in replaced:
            raise ValueError('duplicate Edge package identity: ' + key)
        replaced.add(key)
        families.setdefault(kind, set()).add(version(key, filename))
    if set(families) != set(edgelib.FAMILIES) or any(len(versions) != 1 for versions in families.values()):
        raise ValueError('the Edge build must carry one version of the kernel and one of Mesa')
    keep = sorted(filename for key, filename in base if key not in replaced)
    if len(keep) + len(replaced & {key for key, _ in base}) != len(base):
        raise ValueError('duplicate base package identity')
    # Every kernel and Mesa family package of the base must come from the Edge build;
    # a base-only subpackage would ship at the Testing version beside it.
    stale = sorted(filename for key, filename in base
                   if key not in replaced and edgelib.family(key.rsplit('.', 1)[0]) is not None)
    if stale:
        raise ValueError('Testing kernel or Mesa packages the Edge build has not replaced: ' + ', '.join(stale))
    add = sorted(filename for _, filename in edge)
    if sources:
        return keep, add, {filename: origin.get(filename, 'edge') for filename in add}
    return keep, add


def packaged_sources(sources, trees, mesa_sources=None):
    kernel = sources['kernel-aurora']['commit']
    mesa_pins = mesa_sources or sources
    mesa = {mesa_pins[name]['commit'] for name in ('mesa-aurora', 'mesa-aurora-fex-guest') if name in mesa_pins}
    if len(mesa) != 1:
        raise ValueError('the Edge build must package one Mesa revision')
    return {'linux': edgelib.source('linux', kernel, trees['linux']),
            'mesa': edgelib.source('mesa', mesa.pop(), trees['mesa'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True, help='downloaded Testing snapshot RPMs')
    parser.add_argument('--edge', type=Path, required=True, help='the Edge signer RPMs')
    parser.add_argument('--sources', type=Path, required=True, help='sources.json the Edge RPMs were packaged from')
    parser.add_argument('--mesa-edge', type=Path, help='the Mesa replacement signer RPMs, when the pair has one')
    parser.add_argument('--mesa-sources', type=Path, help='sources.json the replacement Mesa was packaged from')
    parser.add_argument('--mesa-signing-run', type=int)
    parser.add_argument('--trees', type=Path, required=True, help='{"linux": tree, "mesa": tree} resolved from GitHub')
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-release', required=True)
    parser.add_argument('--signing-run', type=int, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('use a fresh output directory')
    base = [(identity(path), path.name) for path in sorted(args.base.glob('*.rpm'))]
    edge = [(identity(path), path.name) for path in sorted(args.edge.glob('*.rpm'))
            if not path.name.endswith(('.src.rpm', '.nosrc.rpm'))]
    if bool(args.mesa_edge) != bool(args.mesa_sources) or bool(args.mesa_edge) != bool(args.mesa_signing_run):
        parser.error('a Mesa replacement needs its RPMs, sources and signing run together')
    mesa = None if not args.mesa_edge else [
        (identity(path), path.name) for path in sorted(args.mesa_edge.glob('*.rpm'))
        if not path.name.endswith(('.src.rpm', '.nosrc.rpm'))]
    keep, add, origin = plan(base, edge, mesa, sources=True)
    args.output.mkdir(parents=True)
    for name in keep:
        shutil.copyfile(args.base / name, args.output / name)
    for name in add:
        shutil.copyfile((args.mesa_edge if origin[name] == 'mesa' else args.edge) / name, args.output / name)
    record = {'schema': 1, 'channel': 'edge', 'base_release': args.base_release,
              'signing_run': args.signing_run, 'mesa_signing_run': args.mesa_signing_run,
              'packaged_sources': packaged_sources(
                  json.loads(args.sources.read_text()), json.loads(args.trees.read_text()),
                  json.loads(args.mesa_sources.read_text()) if args.mesa_sources else None),
              'edge_rpms': add}
    args.record.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print(f'Edge snapshot: {len(keep)} Testing RPMs from {args.base_release}, {len(add)} Edge RPMs')


if __name__ == '__main__':
    main()
