#!/usr/bin/env python3
"""Validate installed private library resolution and RPM dependency isolation."""
from pathlib import Path
import re
import subprocess

out = Path('out')
private = '/usr/lib64/aurora-avd/'
soname = re.compile(r'^\s*lib(?:avcodec|avdevice|avfilter|avformat|avutil|swscale|swresample)\.so')
for app in ('ffmpeg-avd', 'mpv-avd'):
    linked = subprocess.check_output(['ldd', '/usr/bin/' + app], text=True)
    (out / (app + '.ldd')).write_text(linked)
    print(linked)
    libraries = [line for line in linked.splitlines() if soname.match(line)]
    if not libraries or any('=> ' + private not in line for line in libraries):
        raise SystemExit('FFmpeg dependency escaped the private directory: ' + app)
    dynamic = subprocess.check_output(['readelf', '-d', '/usr/bin/' + app], text=True)
    (out / (app + '.dynamic')).write_text(dynamic)
    paths = [line for line in dynamic.splitlines() if 'RPATH' in line or 'RUNPATH' in line]
    if not paths or any('/src' in line or '/stage' in line or '/BUILD' in line for line in paths):
        raise SystemExit('Missing/private build path in installed RPATH: ' + app)
    print('\n'.join(paths))
provides = subprocess.check_output(['rpm', '-q', '--provides', 'ffmpeg-avd'], text=True)
(out / 'ffmpeg-avd.provides').write_text(provides)
print(provides)
if any(soname.match(line) for line in provides.splitlines()):
    raise SystemExit('Private FFmpeg must not provide global SONAME dependencies')
