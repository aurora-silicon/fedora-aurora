# AVD userspace qualification

The packages are opt-in candidates. System FFmpeg, mpv and browser preferences
are unchanged. This change does not assert that any machine passed hardware
qualification. Use one video at a time and retain decode/reset failures.

## Package layout and source identity

`ffmpeg-avd` contains FFmpeg 8.1 plus the public 13-commit Request API series
from [Kwiboo/FFmpeg](https://github.com/Kwiboo/FFmpeg/compare/n8.1...b57fbbe50c9b2656fad86a1a7eeabfd2b2a50935).
`packages/ffmpeg-avd/provenance.json` pins every commit and the patch hash.
`mpv-avd` is built from the same SRPM against those private libraries, so the
system mpv does not need an ABI-changing FFmpeg replacement. A small mpv
proposal patch separates the request decoder context from the DRM renderer
context for direct import; its existing copy mode already creates a decoder
context independently. Both paths still need target qualification. Private libraries
live in `/usr/lib64/aurora-avd` with executable/library RUNPATHs and no ldconfig
entry, public headers, pkg-config files or global SONAME provides.

`libva-v4l2-request` installs the pinned driver in
`/usr/lib64/aurora-avd/va/v4l2_request_drv_video.so`. Only `avd-vaapi` selects it.
It exports `LIBVA_DRIVER_NAME=v4l2_request` and that private driver search path
for the child command. It changes no global environment or application settings.
Existing browser processes must be closed by the tester before this launch, or
they may reuse a process that did not receive the environment.

License check: FFmpeg is configured without GPL/nonfree components and carries
its LGPL-2.1-or-later license. mpv is GPL-2.0-or-later. The pinned bridge
`4f60c51f7841dd74bb61c94a4ad31e630bbdab01` declares GPL-3.0 in meson.build,
ships GPLv3 COPYING, and its driver sources have GPL-3.0-or-later SPDX headers.
It is **not MIT or LGPL**. The RPM records GPL-3.0-or-later and includes COPYING;
its SRPM contains the corresponding pinned source. The small launcher is MIT.
Do not describe or distribute this fork as an MIT/LGPL driver. A requirement
for an MIT/LGPL-only bridge remains unmet by this candidate.

## Build on Fedora or the controller buildbox

The repository's normal source-hash validation and RPM receipt workflow applies:

```sh
AURORA_INSTALL_BUILDDEPS=1 AURORA_BUILD_JOBS=8 bash scripts/build-rpm ffmpeg-avd
AURORA_INSTALL_BUILDDEPS=1 AURORA_BUILD_JOBS=8 bash scripts/build-rpm libva-v4l2-request
```

Inside a controller build slot with arm64-capable Docker, run
`bash scripts/build-avd-fedora 44` or `bash scripts/build-avd-fedora 45`.
This builds aarch64 binary RPMs and SRPMs, runs package checks, installs them in
the disposable container, and prints hwaccels, library resolution and RPM files.
No CI dispatch is needed. No repository publication or COPR upload is performed
by this draft. Feed the SRPMs to the existing release pipeline only after review.

## Lead install and device identity

Use Fedora 44 aarch64 artifacts on the two Fedora 44 machines and Fedora 45
artifacts on the two Fedora 45 machines. Run these commands locally on the
selected target under the lead's controller authorization. All playback tests
below disable audio; leave the existing speaker protection active.

Copy the three candidate RPMs and short, licensed test clips into a new directory.
Install only the matching distribution's artifacts:

```sh
rpm -E '%fedora'
uname -m
rpm -q ffmpeg-free mpv firefox chromium > system-packages.before.txt 2>&1
sudo dnf install ./ffmpeg-avd-[0-9]*.aarch64.rpm ./mpv-avd-[0-9]*.aarch64.rpm \
  ./libva-v4l2-request-[0-9]*.aarch64.rpm
sudo dnf install v4l-utils libva-utils
v4l2-ctl --list-devices
for node in /dev/video*; do v4l2-ctl -d "$node" -D; done
for node in /dev/media*; do media-ctl -d "$node" -p; done
```

Identify the `avd` M2M decoder and the media topology that contains its exact
video major/minor. Do not assume video0/media0 or select a camera. Assign those
verified paths below, and choose the GPU's render node from `ls -l /dev/dri`:

```sh
VIDEO=/dev/video0       # replace with the identified AVD video node
MEDIA=/dev/media0       # replace with its topology-linked media controller
RENDER=/dev/dri/renderD128  # replace with the identified render node
v4l2-ctl -d "$VIDEO" --list-formats-out
media-ctl -d "$MEDIA" -p
ffmpeg-avd -hide_banner -hwaccels
mpv-avd --no-config --hwdec=help
ldd /usr/bin/ffmpeg-avd
ldd /usr/bin/mpv-avd
```

Require `v4l2request` in FFmpeg's list, the request modes in mpv, and every
libav*/libsw* dependency of these commands under `/usr/lib64/aurora-avd`.
Normal `/usr/bin/ffmpeg` (if installed), `/usr/bin/mpv` and their dependencies
must remain their previous packages. Save the outputs with the RPM NEVRAs and
artifact hashes. Device capability listing alone is not a decode result.

## FFmpeg and mpv, one clip at a time

For each available short H.264, HEVC, VP9 and AV1 clip:

```sh
CLIP=demo-h264-4k30.mp4  # repeat with each codec's clip
ffmpeg-avd -nostdin -hide_banner -loglevel verbose -hwaccel v4l2request \
  -i "$CLIP" -map 0:v:0 -an -frames:v 120 -f null - 2>&1 | tee ffmpeg-request.log
mpv-avd --no-config --no-audio --hwdec=v4l2request --length=4 \
  --msg-level=vd=debug --log-file=mpv-request.log "$CLIP"
# The existing copy mode separates decode from renderer import problems:
mpv-avd --no-config --no-audio --hwdec=v4l2request-copy --length=4 \
  --msg-level=vd=debug --log-file=mpv-request-copy.log "$CLIP"
```

FFmpeg's terminal null output exercises decode; mpv's
normal request mode exercises DRM-PRIME import. Require a completed frame count,
explicit selected hardware decoder in logs, and the AVD video/media fds open by
the player during playback (`lsof "$VIDEO" "$MEDIA"`). Check kernel logs for
errors, timeouts and resets after each clip. Keep failed runs and compare frame
hashes against software decode before claiming correctness. CPU load alone does
not prove hardware use. For an 8-bit clip, compare normalized output bytes:

```sh
ffmpeg-avd -nostdin -hwaccel v4l2request -hwaccel_output_format drm_prime   -i "$CLIP" -an -frames:v 120 -vf 'hwdownload,format=nv12' -f framemd5 hw.md5
ffmpeg-avd -nostdin -hwaccel none -i "$CLIP" -an -frames:v 120   -vf format=nv12 -f framemd5 sw.md5
awk '!/^#/ {print $NF}' hw.md5 > hw.hashes
awk '!/^#/ {print $NF}' sw.md5 > sw.hashes
diff -u sw.hashes hw.hashes
```

For 10-bit capture use the negotiated software transfer format (for example
`p010le`) in both filters and record it. A rejected download/import is a failure,
not a reason to substitute a software decode and call it hardware. M1 Pro and M2 have no AV1 hardware; record AV1 as expected
unsupported hardware there and use `--hwdec=no` for their software baseline.
HEVC depends on the kernel exposing S265; record unsupported if it is absent.

## VA-API and browsers

```sh
avd-vaapi vainfo --display drm --device "$RENDER" 2>&1 | tee vainfo-avd.log
avd-vaapi mpv --no-config --no-audio --hwdec=vaapi --length=4 \
  --msg-level=vd=debug --log-file=mpv-vaapi.log "$CLIP"
```

`vainfo` must name the bridge and report the profiles supported by that node.
This is enumeration evidence, not decoded-frame correctness. To use visl on a
separate test host where it is already provisioned, identify its video/media
pair by `v4l2-ctl --list-devices` and `media-ctl -p`, then run the same `vainfo`
command with the host's render node. visl produces synthetic frames, so it
cannot validate real decoder output or AVD performance. A buildbox without visl
or a render node cannot supply this check.

Firefox requires the proposal in [firefox/README.md](firefox/README.md) to be
reviewed and built with V4L2 enabled. Stock Firefox is a useful denial baseline.
Do not disable the RDD sandbox. Start a separate empty test profile after any
previous instance using that profile has exited:

```sh
printf '%s\n' '<!doctype html><meta charset="utf-8"><video controls muted src="demo-h264-4k30.mp4"></video>' > video-test.html
mkdir -p "$PWD/firefox-avd-profile"
MOZ_LOG='PlatformDecoderModule:5,FFmpegVideo:5' \
  avd-vaapi firefox --no-remote --profile "$PWD/firefox-avd-profile" \
  about:support "file://$PWD/video-test.html"
```

Use the existing `media.ffmpeg.vaapi.enabled` preference if the Fedora build
requires it. Use `media.hardware-video-decoding.force-enabled` only as an
explicit test of the existing browser preference, recording its value. Neither
is written by the package. In `about:support`, save the Media codec support and
Graphics hardware video decoding decision. Play a muted local HTML video with
controls (set the `<video muted>` attribute before assigning its source), then
save decoder logs, the RDD fd list and `Seccomp: 2` from
`/proc/<RDD_PID>/status`. Verify AVD video/media fds and no camera fd. A favorable
about:support row alone does not establish that the clip decoded in hardware.

Chromium is a separate qualification path, because this Firefox patch does not
change Chromium's device broker:

```sh
avd-vaapi chromium --user-data-dir="$PWD/chromium-avd-profile" \
  --mute-audio --enable-features=VaapiVideoDecoder about:gpu "file://$PWD/video-test.html"
```

Record Video Acceleration Information from `about:gpu` and the selected video
decoder from `chrome://media-internals` during the same muted local clip. Retain
broker denials. Do not use `--no-sandbox` or `--disable-gpu-sandbox`. If Chromium
cannot open the media node, report that gap; this proposal does not establish
Chromium hardware playback.

## Rollback

Close candidate players/browsers and launch the normal applications directly.
To remove the candidates:

```sh
sudo dnf remove ffmpeg-avd mpv-avd libva-v4l2-request
```

Review the DNF transaction before accepting it. No global environment, browser
preferences, boot configuration, kernel, device permissions or speaker services
are changed by these packages. Retain package/build/decode failures and the
system package inventory. This draft has made no target-machine changes.
