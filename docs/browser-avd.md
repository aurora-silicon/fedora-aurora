# Fedora 45 browser AVD candidates

These are opt-in candidates for aarch64. No target results are implied by a
build or an offline fixture. The lead runs the target commands under the
controller's authorization. Keep audio muted and retain failures. No system
environment, default profile, device permission or sandbox-disabling option is
installed. AI-assisted implementation and documentation; security review is
still required.

## Source and package identities

| Component | Reviewed input |
| --- | --- |
| Bridge | `omacom/libva-v4l2_request` `4f60c51f7841dd74bb61c94a4ad31e630bbdab01`, GPL-3.0-or-later |
| Fedora Firefox | [dist-git](https://src.fedoraproject.org/rpms/firefox/tree/054f5ce6c099dfc8d788332920b4cb3397334ab6), 159.0-2.fc45 |
| Firefox source | [159.0 release archive](https://archive.mozilla.org/pub/firefox/releases/159.0/source/firefox-159.0.source.tar.xz), SHA512 from the pinned Fedora `sources` file |
| Fedora Chromium | [dist-git](https://src.fedoraproject.org/rpms/chromium/tree/f202a8d8a1af53c6e462ee2034c947bd8c936e2f), 156.0.8078.79-1.fc45 |
| Chromium source | [156.0.8078.79](https://chromium.googlesource.com/chromium/src/+/refs/tags/156.0.8078.79/) |

Both spec deltas add `%bcond avd_request 0`. Building with `--with avd_request`
applies the corresponding source patch and adds `.avd1` to the RPM release.
Default builds retain their previous behavior. Nothing here publishes a COPR,
updates a system browser or creates a new PR. The bridge driver code is
unchanged. Bridge RPM release 4 fixes only the offline process-cleanup
fixture's PID-file publication race, retaining its assertions and deadlines.

## VA-API verdict and expected enumeration

**Target verdict: pending.** There is no J616s/Neo `vainfo`, decoded-frame or
browser result from this work. Native V4L2 Request API success through FFmpeg
does not prove the VA-API translation, surface export or browser sandbox path.

The pinned driver's source predicts these decode entries, conditional on the
selected decoder's formats and controls. This table is not captured `vainfo`:

| Codec | Expected `VAEntrypointVLD` profiles | Target decode verdict |
| --- | --- | --- |
| H.264 | `VAProfileH264ConstrainedBaseline`, `VAProfileH264Main`, `VAProfileH264High` if S264 is exposed | Pending |
| HEVC | `VAProfileHEVCMain` if S265 is exposed; `VAProfileHEVCMain10` only after the driver's 10-bit probe | Pending |
| VP9 | `VAProfileVP9Profile0`, `VAProfileVP9Profile2` if VP9F is exposed | Pending |
| AV1 | `VAProfileAV1Profile0` if AV1F is exposed | Pending on J616s/Neo; no AV1 hardware on M1 Pro/M2 |

H.264 High 10 remains off unless separately selected and qualified. VP9 Profile
2 advertisement is not evidence of working 10-bit output. `VAProfileNone` is
also returned by the profile query; its VideoProc entrypoint depends on finding
a converter. Do not count it as a decode profile or require it for AVD.
The existing bridge pin already contains the Chromium early-export fix. No new
driver decode defect has been reproduced here, so no speculative driver change
is included.

On the selected Fedora 45 target, install the matching bridge and ffmpeg-avd
artifacts described in [avd-userspace.md](avd-userspace.md), plus `libva-utils`
and `v4l-utils`. Record the RPM NEVRAs and clip hashes. Identify the AVD video
node and its topology-linked media controller, rather than assuming node zero:

```sh
rpm -E '%fedora'
uname -m
rpm -q firefox chromium ffmpeg-avd libva-v4l2-request
v4l2-ctl --list-devices
for node in /dev/video*; do v4l2-ctl -d "$node" -D; done
for node in /dev/media*; do media-ctl -d "$node" -p; done
ls -l /dev/dri
```

Set these to the identified AVD pair and GPU render node. The child-scoped
media selection avoids accidentally testing a different decoder:

```sh
VIDEO=/dev/video0             # replace after checking the identity
MEDIA=/dev/media0             # replace with its topology-linked controller
RENDER=/dev/dri/renderD128    # replace with the GPU render node
RUN_DIR=$(mktemp -d "$PWD/browser-avd.XXXXXX")
set -o pipefail
v4l2-ctl -d "$VIDEO" --list-formats-out > "$RUN_DIR/formats.txt"
media-ctl -d "$MEDIA" -p > "$RUN_DIR/topology.txt"
LIBVA_V4L2_REQUEST_MEDIA_PATH="$MEDIA" avd-vaapi \
  timeout 30s vainfo --display drm --device "$RENDER" 2>&1 | tee "$RUN_DIR/vainfo.log"
```

Require the `v4l2-request` vendor, expected decode entries and a successful
initialization. Preserve an initialization failure as the verdict for that
attempt. Profile enumeration alone is insufficient.

Run this next block once per short, licensed clip, sequentially. Use `CODEC=h264`,
`hevc`, `vp9` or `av1`, and select a matching clip. Start with 8-bit 4:2:0 and
`PIX_FMT=nv12`. For a separately qualified 10-bit capture use `p010le` in both
commands. Explicitly selecting the native `av1` decoder avoids libdav1d being
chosen instead of the VA-API-capable decoder.

```sh
CODEC=h264
CLIP=/absolute/path/to/h264-8bit.mp4
PIX_FMT=nv12
CASE_DIR=$(mktemp -d "$RUN_DIR/$CODEC.XXXXXX")
JOURNAL_START=$(date --iso-8601=seconds)
sha256sum "$CLIP" > "$CASE_DIR/clip.sha256"
ffprobe-avd -v error -show_streams "$CLIP" > "$CASE_DIR/streams.txt"
timeout 60s ffmpeg-avd -nostdin -hide_banner -loglevel verbose -xerror \
  -hwaccel none -c:v "$CODEC" -i "$CLIP" -map 0:v:0 -an -sn -dn \
  -frames:v 120 -vf "format=$PIX_FMT" -f framemd5 "$CASE_DIR/sw.md5" \
  2> "$CASE_DIR/sw.log"
LIBVA_V4L2_REQUEST_MEDIA_PATH="$MEDIA" avd-vaapi \
  timeout 60s ffmpeg-avd -nostdin -hide_banner -loglevel verbose -xerror \
  -hwaccel vaapi -hwaccel_device "$RENDER" -hwaccel_output_format vaapi \
  -c:v "$CODEC" -i "$CLIP" -map 0:v:0 -an -sn -dn -frames:v 120 \
  -vf "hwdownload,format=$PIX_FMT" -f framemd5 "$CASE_DIR/hw.md5" \
  2> "$CASE_DIR/hw.log"
hw_rc=$?
printf '%s\n' "$hw_rc" > "$CASE_DIR/hw.exit"
sudo journalctl -k --since "$JOURNAL_START" --no-pager > "$CASE_DIR/kernel.log"
awk '!/^#/ && NF {print $NF}' "$CASE_DIR/sw.md5" > "$CASE_DIR/sw.hashes"
awk '!/^#/ && NF {print $NF}' "$CASE_DIR/hw.md5" > "$CASE_DIR/hw.hashes"
wc -l "$CASE_DIR/"*.hashes
diff -u "$CASE_DIR/sw.hashes" "$CASE_DIR/hw.hashes" > "$CASE_DIR/hash.diff"
```

A pass requires exit zero, 120 frames in **both** files, equal hashes and a
VA-API decoder in the log. Empty files or two matching truncated files do not
pass. `hwdownload` with VA surfaces makes software fallback fail this command.
Record AVD fds during the run and any new kernel error/reset. Preserve timeout,
decode and hash failures. Do not repeatedly reopen a faulted decoder or reload
its module to manufacture a pass. A rejected transfer is a distinct failure
from a codec submission failure.

## Firefox package and lead run

The existing [RDD source proposal](firefox/0001-rdd-v4l2-request-proposal.patch)
applies to the exact 159.0 source files. It admits M2M video nodes, topology-linked
media nodes and exact video sysfs uevents, plus four media/request ioctls. It
does not grant a media prefix or disable RDD. Firefox 159's
`toolkit/moz.configure` already defines `MOZ_ENABLE_V4L2` on GTK/aarch64; there
is no `--enable-v4l2` configure option in this revision.

Fedora's [FFmpeg 9.0.2 recipe](https://src.fedoraproject.org/rpms/ffmpeg/tree/be22e49dabfc1c7e3335c6401e099c6d3a030b7a)
disables native `h264` and `hevc` decoders in its default free-codec build.
The OpenH264 decoder has no VA-API hwconfig. Firefox normally loads system
libavcodec by SONAME, so installing `ffmpeg-avd` does not select its private
FFmpeg 8.1 libraries for Firefox. The separate
[private-library patch](firefox/0002-opt-in-private-ffmpeg.patch), applied only
by the candidate RPM, adds `MOZ_AVD_FFMPEG=1` on GTK/aarch64. That exact value
selects only `/usr/lib64/aurora-avd/libavcodec.so.62`; a missing/unusable library
fails instead of substituting the system codec library. Without the switch,
the original search list is used and the private library is skipped.
The library's own private RUNPATH resolves its FFmpeg dependencies. This does
not set `LD_LIBRARY_PATH` or replace any system FFmpeg library. Keep the two
patches separate when reviewing the minimal sandbox change.

Prepare a clean checkout and build on Fedora 45 aarch64:

```sh
git clone --branch f45 https://src.fedoraproject.org/rpms/firefox.git firefox-f45
git -C firefox-f45 switch -c avd-request 054f5ce6c099dfc8d788332920b4cb3397334ab6
python3 docs/firefox/prepare-fedora.py firefox firefox-f45
cd firefox-f45
fedpkg --release f45 sources
sudo dnf builddep firefox.spec
rpmbuild -ba --with avd_request --define "_sourcedir $PWD" \
  --define '_smp_build_ncpus 8' --define '_smp_mflags -j8' firefox.spec
```

For a controller build slot, use `scripts/build-firefox-avd-fedora` inside a
disposable Fedora 45 aarch64 container with `BUILD_OUT` set. It verifies the
pinned dist-git input, fetches Fedora's hash-checked lookaside sources, builds
the candidate RPM/SRPM, and preserves build/configuration failures. This is a
build recipe, not a statement that an RPM or full test suite passed; consult
the worker's build receipt for the actual outcome.

Before installing a candidate, preserve the exact stock Firefox and matching
langpack RPMs for rollback and inventory their NEVRAs. Install the matching
`.fc45.avd1.aarch64.rpm` set only after reviewing the DNF transaction. Keep a
stock-browser evidence run and a patched-browser run with separate profiles.
For the pinned package, with the main and langpack artifacts in this directory:

```sh
sudo dnf install ./firefox-159.0-2.fc45.avd1.aarch64.rpm \
  ./firefox-langpacks-159.0-2.fc45.avd1.aarch64.rpm
```

Use VP9 with `MOZ_AVD_FFMPEG` absent in both runs to isolate the sandbox delta
against the same system codec library. Then use the candidate with
`MOZ_AVD_FFMPEG=1` for the four-codec matrix. Stock Firefox ignores the new
switch; its missing H.264/HEVC native decoder is a separate baseline failure.

Repeat this setup block for every stock/candidate browser and codec attempt.
It creates a new evidence directory and muted local page:

```sh
BROWSER_RUN_DIR=$(mktemp -d "$RUN_DIR/browser.XXXXXX")
BROWSER_JOURNAL_START=$(date --iso-8601=seconds)
sha256sum "$CLIP" > "$BROWSER_RUN_DIR/clip.sha256"
python3 - "$CLIP" "$BROWSER_RUN_DIR/video.html" <<'PY'
import html, sys
from pathlib import Path
uri = html.escape(Path(sys.argv[1]).resolve().as_uri(), quote=True)
Path(sys.argv[2]).write_text(
    '<!doctype html><meta charset="utf-8"><video controls muted src="' + uri + '"></video>')
PY
FIREFOX_PROFILE=$(mktemp -d "$BROWSER_RUN_DIR/firefox-profile.XXXXXX")
cat > "$FIREFOX_PROFILE/user.js" <<'PREFS'
user_pref("media.ffmpeg.vaapi.enabled", true);
user_pref("media.volume_scale", "0.0");
PREFS
LIBVA_V4L2_REQUEST_MEDIA_PATH="$MEDIA" MOZ_AVD_FFMPEG=1 MOZ_SANDBOX_LOGGING=1 \
  MOZ_LOG_FILE="$BROWSER_RUN_DIR/firefox" MOZ_LOG='PlatformDecoderModule:5,FFmpegVideo:5' \
  avd-vaapi firefox --no-remote --profile "$FIREFOX_PROFILE" \
  about:support "file://$BROWSER_RUN_DIR/video.html" 2>&1 | tee "$BROWSER_RUN_DIR/firefox-launch.log"
```

Save `about:support` Media and Graphics sections, including the hardware decode
decision and failure log. Record whether `VIDEO_DECODING_TEST_FAILED` remains.
Play the muted clip and require logs identifying the VA-API decoder and actual
frames. Do not bypass a failed probe using force-enabled preferences for the
acceptance run. Confirm RDD is alive, has `Seccomp: 2`, uses the AVD pair and
has no camera fd. Also confirm `/proc/<RDD_PID>/maps` names the private
libavcodec and libavutil for this explicit run. With its numeric PID selected
from the process list:

```sh
RDD_PID=12345                 # replace with this test profile's RDD process
cat "/proc/$RDD_PID/status" > "$BROWSER_RUN_DIR/rdd-status.txt"
cat "/proc/$RDD_PID/maps" > "$BROWSER_RUN_DIR/rdd-maps.txt"
ls -l "/proc/$RDD_PID/fd" > "$BROWSER_RUN_DIR/rdd-fds.txt"
lsof "$VIDEO" "$MEDIA" > "$BROWSER_RUN_DIR/avd-openers.txt"
```

The selector-only regression can be reproduced on Linux with
`python3 docs/firefox/check-private-ffmpeg.py /path/to/unpatched/firefox-159.0`.
It compiles the actual patched candidate-selection code for simulated
GTK/aarch64 and GTK/x86_64 conditions. It does not test dynamic linkage or
replace a full Firefox compile.

An absent camera fd alone does not prove camera denial. Real broker/seccomp
negative tests must additionally confirm an unrelated camera video/media pair
is denied, unrelated media ioctls remain denied, and stock GPU VA-API/software
playback still work. The helper fixtures do not replace those integration tests.

## Chromium decision and prototype

Choose **native V4L2 stateless** for the Fedora 45 aarch64 prototype. Fedora's
pinned spec already sets `use_v4l2_codec=true` and `use_vaapi=false` on aarch64.
The inspected 156 sources implement Linux decoder selection, so a ChromeOS
port is not the first prerequisite. Two source-proven gaps remain:

1. `AcceleratedVideoDecoder` is disabled by default when VA-API is compiled out.
   Use an explicit launch feature in a fresh profile.
2. Linux `V4L2Device` opens `/dev/video0..255` and `/dev/media0..9`, while the GPU
   and out-of-process decode broker hooks grant `video-decN`/`media-decN` paths.
   The prototype adds exact, bounded topology-linked stateless M2M admission to
   both hooks. No camera prefix, udev symlink, chmod or sandbox switch is used.

The pinned sources for this decision are the
[Linux media client](https://chromium.googlesource.com/chromium/src/+/refs/tags/156.0.8078.79/media/mojo/services/gpu_mojo_media_client_linux.cc),
[feature defaults](https://chromium.googlesource.com/chromium/src/+/refs/tags/156.0.8078.79/media/base/media_switches.cc),
[device discovery](https://chromium.googlesource.com/chromium/src/+/refs/tags/156.0.8078.79/media/gpu/v4l2/v4l2_device.cc),
[GPU broker hook](https://chromium.googlesource.com/chromium/src/+/refs/tags/156.0.8078.79/content/common/gpu_pre_sandbox_hook_linux.cc)
and [decode broker hook](https://chromium.googlesource.com/chromium/src/+/refs/tags/156.0.8078.79/media/gpu/sandbox/hardware_video_decoding_sandbox_hook_linux.cc).

The [prototype patch](chromium/0001-linux-stateless-decoder-broker-prototype.patch)
adds a shared helper to the sandbox policy target. It requires streaming M2M
multiplanar capabilities and a requested stateless coded format, rejects
symlink/regular nodes and unstable/oversized topology, and grants video paths
only when linked by a media controller. Existing ChromeOS permissions and
seccomp behavior remain unchanged. Like the existing broker design, this is
path-based and needs hotplug/replacement security review.

The opt-in [Fedora spec delta](chromium/fedora-45.spec.patch) also sets
`use_av1_hw_decoder=true use_libgav1_parser=true`. Otherwise the V4L2-only
Linux build's default AV1 hardware flag is false. AV1 remains pending on the
actual J616s/Neo. HEVC still depends on the package's HEVC parser/build policy
and the kernel; this patch does not change codec distribution policy.

Prepare/build using the same dist-git process as Firefox:

```sh
git clone --branch f45 https://src.fedoraproject.org/rpms/chromium.git chromium-f45
git -C chromium-f45 switch -c avd-request f202a8d8a1af53c6e462ee2034c947bd8c936e2f
python3 docs/firefox/prepare-fedora.py chromium chromium-f45
cd chromium-f45
fedpkg --release f45 sources
sudo dnf builddep chromium.spec
rpmbuild -ba --with avd_request --define "_sourcedir $PWD" \
  --define '_smp_build_ncpus 8' --define '_smp_mflags -j8' chromium.spec
```

This is a source prototype, not a fully built or qualified Chromium package.
The actual helper is compiled against Linux UAPI by
`python3 docs/chromium/check-prototype.py`, with normal and ASan/UBSan runs.
Full Chromium compilation, GN include checks and broker integration tests
remain required before shipping.

First record stock Chromium with the same feature flags, then the candidate:

```sh
CHROMIUM_PROFILE=$(mktemp -d "$BROWSER_RUN_DIR/chromium-profile.XXXXXX")
chromium --user-data-dir="$CHROMIUM_PROFILE" --mute-audio \
  --enable-features=AcceleratedVideoDecoder,AcceleratedVideoDecodeLinuxGL,PreferV4L2VideoAcceleration \
  --enable-logging=stderr --vmodule='*v4l2*=3,*video_decoder*=2' \
  chrome://gpu chrome://media-internals "file://$BROWSER_RUN_DIR/video.html" \
  2>&1 | tee "$BROWSER_RUN_DIR/chromium.log"
```

Use the existing hardware graphics acceleration setting and record it. The
native path does not use `avd-vaapi`. Save Video Acceleration Information from
`chrome://gpu`, and the active decoder and platform-decoder fields from
`chrome://media-internals` while frames play. `MojoVideoDecoder` alone only
identifies a wrapper; corroborate `V4L2VideoDecoder`/platform decoding with
logs, AVD fds and successful frames. Preserve broker denials and kernel errors.
Do not infer decode from the GPU feature-status row or low CPU usage.

VA-API via the bridge remains an alternative **rebuild**, not a flag-only fix
for this aarch64 package: VA-API is compiled out. Switching backends would also
need the appropriate broker paths and sysfs access for the bridge. It would
add another translation and export path before proving the existing native
backend. No claim is made that either browser is ready to ship yet.

After correctness and sandbox checks pass, repeat the setup and browser run
with a licensed `3840x2160` VP9 clip, then AV1 on AV1-capable hardware. Record
30/60 fps as actually selected, active decoder, AVD fds and visible correctness.
For the local page, capture this browser-console result at the beginning and
end of playback:

```js
const video = document.querySelector('video');
({width: video.videoWidth, height: video.videoHeight,
  quality: video.getVideoPlaybackQuality()});
```

Record total/dropped frames and preserve the decoder logs. For a YouTube 4K
demo, use the same candidate flags and a fresh profile, keep playback muted,
and corroborate Stats for Nerds resolution/fps with the decoder/fd evidence.
Resolution selection alone is not a hardware-decode pass.

After each browser attempt, capture its bounded kernel interval:

```sh
sudo journalctl -k --since "$BROWSER_JOURNAL_START" --no-pager \
  > "$BROWSER_RUN_DIR/kernel.log"
```

Keep raw browser/journal evidence in the local run directory; publish only
redacted codec and sandbox summaries.

## Rollback and evidence

Close candidate browsers. Keep their fresh profiles and all failing logs.
Reinstall/downgrade the saved, matching stock browser RPM set after reviewing
the DNF transaction, then launch stock browsers with a new stock test profile.
For the matching pinned stock Firefox version, for example:

```sh
sudo dnf downgrade ./stock-rpms/firefox-159.0-2.fc45.aarch64.rpm \
  ./stock-rpms/firefox-langpacks-159.0-2.fc45.aarch64.rpm
```

Remove `ffmpeg-avd mpv-avd libva-v4l2-request` if no longer needed, as described
in [the package guide](avd-userspace.md#rollback). No kernel, firmware, boot
setting, speaker service or global configuration change is part of this work.

For each machine/codec record kernel, package hashes/NEVRAs, node identity,
clip hash/format, exact command, exit status, 120-frame hash comparison,
browser diagnostics, sandbox/fd evidence and the bounded kernel log interval.
Record unsupported codec/format separately from a failure of an advertised
profile. Only the lead's physical results can turn the pending rows into passes.
