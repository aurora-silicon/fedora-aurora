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
