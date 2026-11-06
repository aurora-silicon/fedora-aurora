# VA-API over the Apple Video Decoder

Aurora's kernel exposes AVD through the standard V4L2 stateless request API.
GStreamer can use that API directly, but most desktop players and browsers
expect VA-API. `libva-v4l2-request-avd` packages the maintained
`omacom/libva-v4l2_request` AVD fork as that bridge; it does not ship firmware,
kernel code, a browser preference, or a sandbox exception.

## Architecture and ownership

The data path is:

```text
Firefox / Chromium / mpv / GStreamer VA
                  |
                  v
        libva-v4l2_request
       (VA VLD -> requests)
                  |
          media request fd
                  |
                  v
    apple-avd V4L2 mem2mem decoder
       OUTPUT: stateless controls + slices
       CAPTURE: NV12 or P010 DMA-BUF
                  |
                  v
       AGX imports the DMA-BUF planes
```

The kernel contract already has everything this bridge needs: standard H.264,
HEVC, VP9 and AV1 stateless controls; request-capable OUTPUT; MMAP/DMABUF on
both queues; `VIDIOC_EXPBUF`; and linear NV12/P010 CAPTURE formats. No
Aurora-private control or kernel patch is part of this package.

The userspace driver owns VA profile/RT-format reporting, request construction,
surface lifetime and the `VADRMPRIMESurfaceDescriptor`. Its early-export path
keeps one backing allocation for a VA surface so Chromium can import the
DMA-BUF before the first decode. Linear NV12 and P010 are exported with their
real pitch and luma/chroma offsets; the package does not invent a tiling
modifier. A client must fall back when the GPU cannot import the advertised
layout.

The RPM installs both `v4l2_request_drv_video.so` and an
`asahi_drv_video.so` symlink. The latter is libva's normal driver-name lookup
for the AGX render node, so native desktop applications do not need a global
`LIBVA_DRIVER_NAME`. The explicit name remains useful for diagnostics.

## Capability boundary

These rows are expected exposure from the current kernel and backend source,
not hardware qualification. `vainfo` on each machine is the authority. High
10 H.264 stays off by default because its client compatibility mode is opt-in.

| Codec | VA profiles | J616s / T6041 | Neo / T8140 | Boundary |
|---|---|---:|---:|---|
| H.264 | Constrained Baseline, Main, High | expected | expected | progressive 8-bit 4:2:0; interlace and unsupported syntax fall back |
| H.264 High 10 | High10 | opt-in only | opt-in only | not enabled by the Fedora package |
| HEVC | Main, Main10 | expected | absent | T8140's kernel variant deliberately has no HEVC capability |
| VP9 | Profile 0, Profile 2 | expected | expected | Profile 2 appears only after a 10-bit control and P010 CAPTURE probe pass |
| AV1 | Profile 0 | expected | expected | 8-bit stays available; the 10-bit RT format appears only after the AV1/P010 probe |

AV1 film grain, VP9 inter-frame resizing, H.264 interlace, remaining strict
conformance failures and HDR/display correctness retain their upstream support
status. A profile in `vainfo` means the negotiation path exists, not that every
stream in that profile is qualified.

## Fedora package and discovery

The source commit and archive digest are pinned in `sources.json`. The Meson
build uses `-Dvendor-string=Fedora Aurora`; `vainfo` must therefore identify
`v4l2-request (Fedora Aurora 1.3.r11)`. The image includes the package alongside
`avd-fw`. The alias is a relative symlink in libva's driver directory and is
owned by the RPM, making collisions visible to RPM rather than silently
overwriting another implementation.

This first package covers native RPM applications. Flatpak runtimes have a
separate filesystem and need an explicitly versioned libva-driver extension
before Flatpak Firefox/Chromium can be claimed. Do not weaken a browser sandbox
or export a global environment override to make a smoke test pass.

## Hardware-lane test plan

Run once on J616s and once on Neo with the exact RPM NEVRA, kernel commit,
firmware package and Mesa version recorded. Use licensed redistribution-safe
clips: H.264 8-bit, HEVC Main/Main10 (J616s only), VP9 Profile 0/Profile 2 and
AV1 8/10-bit. For every row record whether decode was hardware, software
fallback, clean rejection, wrong output or a decoder fault. A selected decoder
without correct pixels is not a pass.

1. Inventory and profile truth:

   ```sh
   rpm -q libva-v4l2-request-avd avd-fw kernel-aurora mesa-aurora-dri-drivers
   readlink -f /usr/lib64/dri/asahi_drv_video.so
   env -u LIBVA_DRIVER_NAME vainfo --display drm
   LIBVA_DRIVER_NAME=v4l2_request LIBVA_V4L2_DIAG=json vainfo --display drm
   ```

   Require the Fedora Aurora vendor string, VLD only (no encode claim), the
   machine-specific matrix above, and no advertised 10-bit profile/RT format
   when its probe failed.

2. mpv decode, presentation and fallback:

   ```sh
   mpv --no-config --gpu-api=opengl --hwdec=vaapi --msg-level=vd=debug sample.mkv
   mpv --no-config --gpu-api=opengl --hwdec=vaapi-copy --msg-level=vd=debug sample.mkv
   ```

   Require `Using hardware decoding (vaapi)`, visually correct output and no
   new AVD fault/reset in the bounded journal. Repeat seek-to-start, close and
   reopen. An unsupported clip must fall back or fail cleanly, never wedge the
   decoder. Vulkan presentation is outside this gate.

3. Firefox (native RPM, normal sandbox): play each supported web codec and
   capture `about:support` Graphics/Media plus `MOZ_LOG=PlatformDecoderModule:5`.
   Require a VA-API hardware decoder and correct playback with the normal RDD
   sandbox. If device access is denied, record the denial as a sandbox
   integration failure; do not rerun with the sandbox disabled as a pass.

4. Chromium (native RPM, normal GPU sandbox): record `chrome://gpu` Video
   Acceleration Information and the decoder selected in
   `chrome://media-internals`. Require `VaapiVideoDecoder`, correct pixels,
   seek/reopen recovery and no `GpuVideoDecodeAccelerator` software fallback.
   Do not add `--no-sandbox`, `--disable-gpu-sandbox` or a persistent flag.

5. GStreamer VA and direct-V4L2 comparison:

   ```sh
   gst-inspect-1.0 | grep -E '(^| )va.*dec'
   gst-launch-1.0 -v filesrc location=sample.mkv ! decodebin ! videoconvert ! fakesink sync=false
   ```

   Pin the actual `vah264dec`, `vah265dec`, `vavp9dec` or `vaav1dec` element
   present in the installed GStreamer release and require VA surfaces. Compare
   one matching direct `v4l2sl*dec` run to separate backend health from bridge
   failures.

6. DMA-BUF/export evidence: with driver diagnostics enabled, confirm the
   client exports DRM PRIME 2 surfaces, AGX imports the same NV12/P010 object,
   plane offsets/pitches remain stable across early export, and no CPU-copy
   fallback is counted as zero-copy. Repeat one 8-bit and one 10-bit case.

7. Finish with a bounded kernel-log diff and a second `vainfo`. Require no new
   AVD timeout, reset, IOMMU fault, memory leak trend or lost profile. Preserve
   all failed and partial rows in the lane evidence.

## ALARM and NixOS parity

ALARM already has the same two-package split (`avd-fw` and
`libva-v4l2_request-avd`) and uses the `asahi_drv_video.so` alias. Its source
pin should move to the capability-gated maintained fork before claiming parity;
its earlier Firefox guidance that disables the RDD sandbox is not an Aurora
acceptance path.

`nixos-apple-silicon` packages `libva-v4l2_requests-sofus13` behind
`hardware.asahi.avd.vaapi-support`, currently off by default for stability.
Parity means updating that derivation to the maintained fork, retaining the
opt-in until the same J616s/Neo client matrix passes, and installing the
automatic `asahi` alias without a global environment override. These are notes
for their maintainers; this Fedora branch does not modify either distribution.
