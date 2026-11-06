# VA-API over the Apple Video Decoder

Aurora's kernel exposes AVD through the standard V4L2 stateless Request API.
`libva-v4l2-request-avd` installs the pinned public `omacom/libva-v4l2_request`
AVD branch as the VA-API bridge used by desktop players and browsers. It ships
no firmware, browser preference, global environment variable, or sandbox
exception.

## Driver discovery

The RPM owns both files in libva's system driver directory:

```text
/usr/lib64/dri/v4l2_request_drv_video.so
/usr/lib64/dri/asahi_drv_video.so -> v4l2_request_drv_video.so
/usr/lib64/dri/aurora_drv_video.so -> v4l2_request_drv_video.so
```

The relative aliases match the older and current render-node driver names, so
normal applications select the bridge without `LIBVA_DRIVER_NAME`. The explicit
name remains useful for diagnosis:

```sh
LIBVA_DRIVER_NAME=v4l2_request vainfo --display drm
```

The expected vendor string at the pinned source is
`v4l2-request (omarchy-m1-video 1.3.r11)`. The package retains it so the tested
upstream source can be identified exactly.

## Scope and codec availability

The bridge is decode-only. Its profile list reflects the stateless codec
devices exposed by the running kernel. A profile in `vainfo` proves negotiation,
not correct pixels for every stream. Unsupported syntax must fall back or fail
cleanly. High-10 H.264 remains opt-in upstream and is not enabled by the package.

Fedora's `ffmpeg-free` does not contain H.264 or HEVC decoders. Consequently,
native Fedora Firefox can use this driver for AV1 and VP9, while H.264/HEVC
require a separately supplied full libavcodec. This package does not replace
Fedora multimedia policy. Flatpak applications also need a matching runtime
libva-driver extension; the host RPM alone is not visible inside a Flatpak.

## Hardware-lane verification

Record the RPM NEVRA and SHA-256, kernel, firmware package, Mesa, libva and
client versions. Keep failed and fallback runs as evidence.

1. Confirm discovery and profiles:

   ```sh
   rpm -q libva-v4l2-request-avd avd-fw kernel-aurora mesa-aurora-dri-drivers libva
   readlink /usr/lib64/dri/asahi_drv_video.so
   readlink /usr/lib64/dri/aurora_drv_video.so
   env -u LIBVA_DRIVER_NAME vainfo --display drm
   LIBVA_DRIVER_NAME=v4l2_request LIBVA_V4L2_DIAG=json vainfo --display drm
   ```

2. For licensed H.264, HEVC, VP9 and AV1 clips, compare normalized decoded
   frames with software. Pick `nv12` or `p010le` to match the stream:

   ```sh
   ffmpeg -v verbose -hwaccel vaapi -hwaccel_output_format vaapi -i sample.mkv \
     -map 0:v:0 -an -vf 'hwdownload,format=nv12' -f framemd5 hardware.framemd5
   ffmpeg -v error -hwaccel none -i sample.mkv -map 0:v:0 -an \
     -vf format=nv12 -f framemd5 software.framemd5
   diff -u software.framemd5 hardware.framemd5
   ```

3. Exercise presentation and the explicit copy path at the lowest usable audio
   volume, or muted. Speaker protection must remain active:

   ```sh
   mpv --no-config --no-audio --hwdec=vaapi --msg-level=vd=debug sample.mkv
   mpv --no-config --no-audio --hwdec=vaapi-copy --msg-level=vd=debug sample.mkv
   ```

4. Run native Firefox with its normal RDD sandbox and a fresh profile. Capture
   the Graphics and Media sections of `about:support` and decoder selection:

   ```sh
   MOZ_LOG_FILE="$PWD/firefox-vaapi" \
   MOZ_LOG='PlatformDecoderModule:5,FFmpegVideo:5' \
     firefox --no-remote --profile "$PWD/firefox-profile" about:support
   ```

   A sandbox denial is a failed integration test. Do not disable the RDD
   sandbox, add a persistent preference, or weaken device permissions.

5. Bound the kernel log before and after each codec. Require no new AVD timeout,
   reset, IOMMU fault, lost profile, or growing resource count. Repeat `vainfo`
   after seek, close and reopen testing.

## Other distributions

ALARM installs the driver under `/usr/lib/dri` with the same relative aliases.
NixOS places it in the graphics driver closure and exposes all three names under
`/run/opengl-driver/lib/dri`. Neither distribution sets a global driver
override. Removal of the package (or of the NixOS graphics package) is the
complete rollback.
