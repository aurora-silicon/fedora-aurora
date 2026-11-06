# Firefox RDD access for V4L2 Request decoders

Firefox 157 already brokers qualifying V4L2 memory-to-memory nodes into the
RDD process when `MOZ_ENABLE_V4L2` is defined. Stateless Request API decoders
also need a topology-linked media-controller node and the exact sysfs uevent
that maps the topology's character-device number back to `/dev/video*`.
`0001-rdd-v4l2-request.patch` adds those dependencies without disabling or
broadening the RDD sandbox.

## Root cause

The failure occurs during VA driver initialization, before a coded frame is
submitted. The public driver implementation:

1. calls `access(F_OK)` and opens `/dev/media0` through `/dev/media63`;
2. uses `MEDIA_IOC_G_TOPOLOGY` to find a V4L video interface;
3. reads `/sys/dev/char/<major>:<minor>/uevent` to resolve its `/dev/video*`;
4. opens that video node and uses `VIDIOC_*` operations to verify Request API
   support; and
5. later allocates, queues and reinitializes request fds with
   `MEDIA_IOC_REQUEST_ALLOC`, `MEDIA_REQUEST_IOC_QUEUE`, and
   `MEDIA_REQUEST_IOC_REINIT`.

Sources: the pinned driver's
[enumeration code](https://github.com/omacom/libva-v4l2_request/blob/4f60c51f7841dd74bb61c94a4ad31e630bbdab01/src/driver.c#L222-L527),
[context setup](https://github.com/omacom/libva-v4l2_request/blob/4f60c51f7841dd74bb61c94a4ad31e630bbdab01/src/context.c#L1048-L1220),
and [request submission](https://github.com/omacom/libva-v4l2_request/blob/4f60c51f7841dd74bb61c94a4ad31e630bbdab01/src/decode.c#L491-L697).

Firefox's existing
[RDD broker policy](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/security/sandbox/linux/broker/SandboxBrokerPolicyFactory.cpp#L884-L946)
adds only M2M `/dev/video*` paths and `/dev` enumeration. It does not add any
`/dev/media*` path or the video node's sysfs uevent. Therefore the first
`access(F_OK)` for the media controller is rejected by the broker and the
driver reports that no Request API decoder was found. If only that path were
added, Firefox's
[RDD seccomp ioctl rule](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/security/sandbox/linux/SandboxFilter.cpp#L2083-L2141)
would allow V4L2 type `V`, DRM type `d`, and dma-buf type `b`, but would still
reject the media/request ioctls (Linux media ioctls use a different type).
File operations are routed through the broker by
[SandboxPolicyCommon](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/security/sandbox/linux/SandboxFilter.cpp#L939-L997).

Firefox 157 enables `MOZ_ENABLE_V4L2` automatically for GTK on aarch64; see
[`toolkit/moz.configure`](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/toolkit/moz.configure#L634-L652).

## Scope of the patch

The parent process keeps the existing webcam boundary: it first identifies
character devices with `V4L2_CAP_VIDEO_M2M` or
`V4L2_CAP_VIDEO_M2M_MPLANE`. A media node is admitted read/write only when a
bounded, stable two-pass topology contains a V4L video interface whose device
number matches that already admitted set. Only the matching video's direct and
canonical sysfs uevent paths are admitted read-only. Media opens reject
symlinks and non-character files. No `/dev/media` prefix, sysfs subtree, camera
exception, permission change, or non-RDD policy is added.

Seccomp gains only the four operations used by this driver:

- `MEDIA_IOC_G_TOPOLOGY`
- `MEDIA_IOC_REQUEST_ALLOC`
- `MEDIA_REQUEST_IOC_QUEUE`
- `MEDIA_REQUEST_IOC_REINIT`

The broader media ioctl family remains denied. Existing V4L2, DRM and dma-buf
rules are unchanged. The RDD sandbox remains enabled.

The patch is MPL-2.0 and targets the public Firefox 157.0.1 release source.
The Fedora delta is pinned to Fedora 44 dist-git commit
`1465e7dfc36e96ec3825c12f3dbed41c426e080d`; it is opt-in so an unqualified
candidate cannot replace Fedora's browser accidentally:

```sh
python3 docs/firefox/prepare-fedora.py /path/to/clean/firefox-distgit
rpmbuild -ba --with avd_request firefox.spec
```

`scripts/build-firefox-rdd-v4l2-request` performs the same pinned preparation
inside a controller build slot. `--source-only` produces an SRPM without a
host build.

## Offline checks

```sh
python3 docs/firefox/check-rdd-v4l2-request.py
python3 -m unittest tests.test_firefox_rdd_v4l2_request
```

The focused C++ harness extracts the production topology helper and covers a
linked decoder, an unrelated controller, non-video interfaces, invalid media
names, regular files, failed calls, zero/oversized topology, and count/version
changes. It does not replace a Firefox compile, broker integration test, or
hardware run.

## ENG hardware recipe

Use the candidate RPM and the packaged `aurora` VA driver. Do not set
`MOZ_DISABLE_RDD_SANDBOX` or change sandbox levels. This creates a fresh
profile and a muted page for every attempt. `CLIP` must be a licensed 4K AV1
WebM whose hash is recorded with the evidence.

```sh
CLIP=/absolute/path/to/4k-av1.webm
RUN_DIR=$(mktemp -d "$PWD/firefox-rdd-av1.XXXXXX")
PROFILE=$RUN_DIR/profile
mkdir -p "$PROFILE"
sha256sum "$CLIP" > "$RUN_DIR/clip.sha256"
cat > "$PROFILE/user.js" <<'PREFS'
user_pref("media.ffmpeg.vaapi.enabled", true);
user_pref("media.hardware-video-decoding.enabled", true);
user_pref("media.av1.enabled", true);
PREFS
python3 - "$CLIP" "$RUN_DIR/play.html" <<'PY'
import html
import sys
from pathlib import Path

uri = html.escape(Path(sys.argv[1]).resolve().as_uri(), quote=True)
Path(sys.argv[2]).write_text(
    '<!doctype html><meta charset="utf-8">'
    f'<video autoplay loop muted controls src="{uri}"></video>'
)
PY
MOZ_ENABLE_WAYLAND=1 \
LIBVA_DRIVER_NAME=aurora \
MOZ_LOG='PlatformDecoderModule:5,FFmpegVideo:5' \
MOZ_LOG_FILE="$RUN_DIR/moz.log" \
firefox --no-remote --profile "$PROFILE" "$RUN_DIR/play.html" \
  >"$RUN_DIR/launch.log" 2>&1
rg -n 'IsHardwareAccelerated=true|vaInitialize failed|no V4L2 Request API decoder' \
  "$RUN_DIR"/moz.log* "$RUN_DIR/launch.log"
```

A pass requires `IsHardwareAccelerated=true` for the AV1 decoder, visible
4K playback without corruption, no VA initialization/device-discovery error,
and an RDD process still running with seccomp filtering enabled. Preserve the
RPM NEVRA, browser version, clip hash, full logs, `/proc/<RDD pid>/status`, and
its fd targets while playback is active. Repeat with a 4K VP9 WebM. A software
fallback, crash, hang, or missing expected log is a failure, not an
inconclusive pass.
