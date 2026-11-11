# Firefox RDD access for V4L2 Request decoders

Firefox 157 already brokers qualifying V4L2 memory-to-memory nodes into the
RDD process when `MOZ_ENABLE_V4L2` is defined. Stateless Request API decoders
also need a topology-linked media-controller node and the exact sysfs uevent
that maps the topology's character-device number back to `/dev/video*`.
`packages/firefox/rdd-v4l2-request.patch` adds those dependencies without
disabling or broadening the RDD sandbox.

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

The broker adds a `/dev/media*` node read/write only when its media
topology contains a V4L video interface whose device number is one of the M2M
video nodes the existing policy already admits, plus that video node's
`/sys/dev/char/<major>:<minor>/uevent` read-only. Camera media nodes, the
`/dev/media` prefix and other sysfs paths stay blocked. Seccomp gains exactly
four ioctls:

- `MEDIA_IOC_G_TOPOLOGY`
- `MEDIA_IOC_REQUEST_ALLOC`
- `MEDIA_REQUEST_IOC_QUEUE`
- `MEDIA_REQUEST_IOC_REINIT`

The rest of the media ioctl family (`MEDIA_IOC_SETUP_LINK`, entity and link
enumeration) stays denied. Existing V4L2, DRM and dma-buf rules are unchanged
and the RDD sandbox stays on. The patch is the one proposed to Mozilla in
[bug 2080696](https://bugzilla.mozilla.org/show_bug.cgi?id=2080696), MPL-2.0.

## Package

`packages/firefox` is Fedora's dist-git recipe for Fedora 44 (`f45/` holds
what differs for Fedora 45), imported by `scripts/import-fedora-firefox.py`.
The import keeps every Fedora file byte for byte and changes `firefox.spec`
only to:

- apply `rdd-v4l2-request.patch` (`Patch900`);
- add `.aurora1` to Fedora's Release, so `firefox-160.0-1.fc44.aurora1`
  replaces Fedora's `firefox-160.0-1.fc44`;
- turn off debuginfo and the WASI SDK build. The WASI SDK compiles its own
  LLVM toolchain inside the Firefox build, which does not fit the hosted
  runner's six hours; without it the wasm-sandboxed third-party libraries
  (RLBox) are built as normal code, as on Fedora's s390x.

Fedora's lookaside archives (`sources`) and its API key files (listed in
`distgit.json` with their SHA-256) are fetched at build time by
`scripts/fetch-fedora-lookaside.py`; the keys are Fedora's and are not copied
into this repository.

The recipe is marked `# aurora-builder: heavy`. Pushes and pull requests never
build it (about three hours on the arm64 runner); a manual `rpms.yml` run with
`packages=firefox` builds it for Fedora 44 and 45 in the `rpm-heavy` job.
Merging that branch with a merge commit lets publication take that build.

## Updates

The Aurora repository has priority over Fedora's, so a Fedora Firefox update
reaches Aurora systems only after it is rebuilt here.
`.github/workflows/track-firefox.yml` runs every two hours: it imports the
current f44/f45 heads, pushes `auto/firefox-<version>-<f44>-<f45>` when they
changed, dispatches its Firefox build and source checks, and on a later run
merges it once both passed and starts publication for both releases. A failed
proposal build fails the workflow. `TRACK_FIREFOX=false` stops the tracker and
`AUTO_MERGE_FIREFOX=false` keeps proposals unmerged.

To import by hand:

```sh
python3 scripts/import-fedora-firefox.py          # clones f44 and f45
python3 scripts/import-fedora-firefox.py --check  # is packages/firefox current?
```

## Checks

`tests/test_firefox.py` covers the spec edit, the fetched key files and the
patch's broker and seccomp scope. The hardware check plays muted H.264, HEVC,
VP9 and AV1 clips in a fresh profile and requires `IsHardwareAccelerated=true`,
the RDD process holding the decoder's `/dev/media*` and `/dev/video*` nodes
with `Seccomp: 2`, no camera media node, and no new SELinux denial.
