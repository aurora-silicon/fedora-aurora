# VA-API decode over the Aurora AVD driver

## Decision

Package Aurora's public `libva-v4l2_request` branch as the VA-API translation
layer for the AVD V4L2 stateless Request API device. The package does not patch,
replace or configure the kernel or firmware. It installs the canonical
`v4l2_request_drv_video.so` module and a DRM driver-name alias so normal libva
DRM display discovery works without a global environment variable.

The source base is the maintained AVD-focused fork at version 1.3.r11. Aurora's
branch adds truthful per-decoder 10-bit reporting: HEVC Main10 and VP9 Profile 2
are advertised only when the same request decoder exposes a usable P010 capture
format, and context selection reuses that capability result. The package vendor
string is `v4l2-request (Aurora 1.3.r11)`.

## Kernel interface audit

Aurora Linux integration already supplies every interface needed by the
backend, so this change carries no kernel branch:

| Requirement | Aurora AVD interface | Result |
| --- | --- | --- |
| Stateless submission | Media requests plus codec controls for H.264, HEVC, VP9 and AV1 | Ready |
| Queue model | Multi-planar streaming M2M OUTPUT/CAPTURE | Ready |
| Multi-slice pictures | HOLD_CAPTURE on H.264 and HEVC | Ready |
| Displayable capture | Linear NV12 and P010 | Ready |
| Client-owned surfaces | CAPTURE accepts DMA-BUF | Ready |
| Exported surfaces | `VIDIOC_EXPBUF` through videobuf2 DMA-contig | Ready |
| Private decoder state | Codec-specific `sizeimage` tail is reported by `S_FMT` | Ready; the backend preserves it outside the visible DRM layers |

The data path is VA picture parameters to request controls and compressed
OUTPUT buffers, then AVD writes linear NV12/P010 CAPTURE buffers. The backend
exports those buffers as DRM PRIME objects with explicit plane offsets, pitches
and the linear modifier. Chromium's early-export pattern is covered by the
source branch: a surface exported before its first decode becomes the actual
DMA-BUF CAPTURE backing rather than a separate decoder allocation.

## Capability and claim matrix

Every row remains experimental until the Aurora hardware plan records exact
pixels, client selection, kernel logs and provenance. Advertising a VA profile
or compiling a codec is not a support claim.

| Codec | VA profiles | Capture | Initial boundary |
| --- | --- | --- | --- |
| H.264 | Constrained Baseline, Main, High | NV12 | Progressive 8-bit 4:2:0; interlace and 4:2:2 are not claimed. High10 stays opt-in and is not enabled by this package. |
| HEVC | Main, Main10 | NV12, P010 | Progressive 4:2:0. Main10 requires accepted 10-bit controls and P010 on the same decoder. Remaining reference-picture correctness failures block a supported tier. |
| VP9 | Profile 0, Profile 2 | NV12, P010 | 8/10-bit 4:2:0. Profile 2 now requires P010 on the same decoder. Inter-frame resize and scalable streams remain outside the initial claim. |
| AV1 | Profile 0 | NV12, P010 | Built only when the kernel UAPI is present and advertised only when AVD exposes AV1. Film grain and full client coverage remain unqualified. |

## Desktop integration

The RPM is included in the common image package set. Automatic selection uses
the DRM driver-name alias; explicit diagnostics can still use
`LIBVA_DRIVER_NAME=v4l2_request`. The package does not set that variable
system-wide and does not weaken Firefox RDD, Chromium GPU, seccomp or SELinux
sandboxing. A browser failure under its normal sandbox is a failed qualification
row and belongs to a separate, narrowly reviewed browser integration change.

Removal is the rollback: uninstalling `libva-v4l2-request` removes the module
and alias and returns clients to their prior software path. It leaves the
kernel, firmware, Mesa and browser configuration untouched.

## Distribution parity

- Fedora Aurora: this repository owns the pinned RPM, source checksum, image
  inclusion and rollback above.
- Arch Linux ARM: build the same public commit with Meson, install the canonical
  module plus the same DRM-name alias in libva's driver directory, depend on
  libva, and rebuild on a libva driver-ABI bump. Do not ship browser sandbox
  overrides.
- NixOS: package the same commit, expose both module names in the driver output,
  add it through `hardware.graphics.extraPackages`, and keep rollback to the
  previous system generation. Do not set a global driver environment variable
  or browser sandbox exception.

## Qualification gate

The hardware lane must retain the exact RPM/source/kernel identities, the full
suite denominators and every failure. It must prove hardware frames rather than
software fallback for `vainfo`, mpv direct and copy modes, the GStreamer `va`
decoders, Chromium and Firefox. NV12 and P010 DMA-BUF import must be checked
separately, as must early-export surfaces. New decoder kernel errors, an AVC,
wrong pixels, a sandbox bypass, or an unexplained reset prevents promotion.


## J616s and Neo hardware qualification plan

This is a future hardware-lane plan, not evidence from this source task. Run it
on both J616s and Neo against one exact candidate RPM. Do not gate on display
state, keyboard backlight, idle time, login/session state, playback state or
time of day. No audio is needed: every player command uses `--no-audio` or a
silent sink. Do not change the kernel, firmware, Mesa, browser sandbox or global
environment during the run.

### Record and preflight

1. Record machine identity, kernel package and boot ID; the RPM NEVRA, source
   commit and file hashes; libva, Mesa, browser, mpv, FFmpeg and GStreamer
   versions; the render node; AVD video/media nodes; SELinux mode; and a journal
   cursor. Locate AVD through `media-ctl -p`, not a hard-coded video number.
2. Save `v4l2-ctl --all`, coded and capture format enumeration, and controls for
   the AVD node. Require Request API support, NV12/P010 capture, DMA-BUF, and
   H.264/HEVC/VP9 plus AV1 only on machines where the kernel advertises it.
3. Use checksum-pinned, licensed corpus inputs and retain the full suite
   denominator. Include progressive 8-bit H.264, HEVC Main/Main10, VP9 Profile
   0/2 and AV1 8/10-bit rows, plus known unsupported interlace, resize, film
   grain or format boundaries. Never count rejection or software fallback as a
   hardware pass.

### VA discovery and profiles

Run both automatic discovery and explicit selection:

```sh
env -u LIBVA_DRIVER_NAME vainfo --display drm --device /dev/dri/renderD128
LIBVA_DRIVER_NAME=v4l2_request vainfo --display drm --device /dev/dri/renderD128
```

Both must identify `v4l2-request (Aurora 1.3.r11)`. The expected initial rows
are H.264 Constrained Baseline/Main/High, HEVC Main/Main10, VP9 Profile 0/2 and
AV1 Profile 0 only where AVD advertises AV1. Main10/Profile 2 must disappear if
P010 is removed from a controlled synthetic capability probe. No encode
entrypoint is expected.

### mpv decode, export and presentation

For each eligible NV12/P010 clip, run direct presentation and readback without
audio. Keep OpenGL; Vulkan is outside this qualification.

```sh
mpv --no-config --no-audio --gpu-api=opengl --hwdec=vaapi \
  --msg-level=vd=debug,vo=gpu,ffmpeg=debug CLIP
mpv --no-config --no-audio --gpu-api=opengl --hwdec=vaapi-copy \
  --msg-level=vd=debug,vo=gpu,ffmpeg=debug CLIP
```

Require the VA hardware decoder in the log, correct visible output, exact
software-reference checksums for the copy path, stable pause/seek/restart/EOS,
and no growth in decoder errors or leaked file descriptors. Exercise a client
that exports every surface before first decode to prove the Chromium-style
early-export backing. Check NV12 and P010 DMA-BUF plane offsets, pitches,
object sizes and linear modifiers separately.

### GStreamer VA elements

First record the registered elements:

```sh
gst-inspect-1.0 va vah264dec vah265dec vavp9dec vaav1dec
```

Then run the applicable elementary-stream parser and decoder to a silent sink,
once preserving VA memory and once downloading to normal video for pixel
comparison. Example H.264 rows are:

```sh
GST_DEBUG='va*:6' gst-launch-1.0 -e filesrc location=CLIP.h264 ! \
  h264parse ! vah264dec ! 'video/x-raw(memory:VAMemory)' ! fakesink sync=false
GST_DEBUG='va*:6' gst-launch-1.0 -e filesrc location=CLIP.h264 ! \
  h264parse ! vah264dec ! video/x-raw,format=NV12 ! fakesink sync=false
```

Repeat with `h265parse ! vah265dec`, `vp9parse ! vavp9dec`, and
`av1parse ! vaav1dec` only where advertised. Require the `va` decoder rather
than `avdec_*` or `v4l2sl*`, hardware-backed surfaces, correct pixels on the
download row and no implicit unsupported-profile claim.

### Firefox with the normal RDD sandbox

Use a disposable profile. Enable `media.ffmpeg.vaapi.enabled` in that profile
only if the packaged browser leaves it off; do not set `MOZ_DISABLE_RDD_SANDBOX`
or any persistent environment override. Start Firefox normally under Wayland,
play the pinned local test page, and save `about:support`.

Require `HARDWARE_VIDEO_DECODING` to be available, the Codec Support Information
rows to match `vainfo`, hardware decode in media diagnostics, correct playback,
and clean pause/seek/reload/close. Record RDD and VA logs plus AVCs. Failure to
open the render, video or media nodes under the normal sandbox is a failed row
and a separate browser-integration follow-up, not permission to weaken the
sandbox.

### Chromium with the normal GPU sandbox

Use a disposable user-data directory and the normal sandbox. Start with the
packaged defaults; if that build exposes VA decode only behind its documented
Linux flags, add only `VaapiVideoDecoder`/`VaapiVideoDecodeLinuxGL`. Never use
`--no-sandbox` or `--disable-gpu-sandbox`.

Save `chrome://gpu` Video Acceleration Information and the relevant
`chrome://media-internals` records. Require `VaapiVideoDecoder`, a hardware
frame pool, correct early-export playback, correct colour, and working
pause/seek/reload/close. A sandbox-denied DRM device-information lookup or AVD
node open is a failed row and owns its own follow-up.

### Acceptance, faults and rollback

For every command, retain the exact environment, exit status, hardware-decoder
selection, pixel/checksum result, resource delta, journal slice and AVC search.
A row passes only with hardware frames, correct pixels, no new AVD/IOMMU/GPU
error, no reset, no leak and an idle decoder afterward. Publish raw pass/total
counts and keep every wrong-output, expected-rejection and unsupported result.

After the matrix, remove the candidate RPM and verify that both driver module
names disappear and clients return to their original software path. The
rollback must not change kernel, firmware, Mesa, browser profiles outside the
disposable directories or any machine-local safety override.
