# Firefox RDD Request API proposal

`0001-rdd-v4l2-request-proposal.patch` is a proposal against mozilla-firefox/firefox
commit `a5df22d986d4b626f771b4f8885241941601c35c`, not an installed Firefox patch.
The two baseline files were fetched publicly and are MPL-2.0. The behavior is
informed by [Mozilla bug 2080696](https://bugzilla.mozilla.org/show_bug.cgi?id=2080696),
reported by Christian Bartels. The implementation here is newly written; the
reporter's patch and device results are not claimed as our validation.

The parent broker already admits M2M video devices to RDD when built with
`MOZ_ENABLE_V4L2`. The proposal records the admitted character-device numbers,
then reads each numbered media controller's topology. It grants read/write only
if a video interface's major/minor matches that admitted set, and read-only
access to that video's exact sysfs uevent (including its canonical path).
No media path prefix, device chmod, udev rule or camera exception is added.
Both topology queries must succeed, agree on version and count, and remain
within 256 interfaces. A missing/changing topology is denied. Media opens reject
symlinks and require character devices. The existing M2M video admission also
gets no-follow/close-on-exec and fstat checks, and honors V4L2_CAP_DEVICE_CAPS.

RDD gains only MEDIA_IOC_G_TOPOLOGY, MEDIA_IOC_REQUEST_ALLOC,
MEDIA_REQUEST_IOC_QUEUE and MEDIA_REQUEST_IOC_REINIT, all behind
MOZ_ENABLE_V4L2. Existing V4L2 'V', DRM and DMA-BUF allowances remain unchanged.
There is no blanket ioctl type '|' permission. Seccomp cannot establish an fd's
topology; the parent broker's restricted device paths provide that boundary.
Request fds are allocated from those media controllers. The proposal does not
change content/GMP/utility policies or disable any sandbox.

The private bridge module sits below `/usr/lib64`, which RDD already reads.
Build Firefox with its existing V4L2 option enabled (`--enable-v4l2`) and confirm
`MOZ_ENABLE_V4L2` in generated configuration. A binary built without it should
retain the baseline denied behavior. Fedora's exact Firefox source version
still needs a rebase/application check before integration into its RPM.

`python3 docs/firefox/check-proposal.py` extracts the actual proposed topology
helper and compiles it on Linux against the media UAPI with mocked OS and
Mozilla container/string calls. Its 16 fixtures cover matching and unrelated
controllers, interface type, missing/oversized/changing topology, failed calls,
regular files and invalid device names. It checks exact granted paths. This
focused harness does not compile Firefox or exercise its real broker/seccomp.

## Required review and test plan

1. In the pinned source, run `git apply --check` and `git apply` with this patch,
   configure a debug Linux aarch64 Firefox with V4L2 enabled, and build with
   `./mach build -j8`. Also compile with V4L2 disabled. Run `./mach lint` for the
   two files and the existing Linux sandbox broker/gtest suites. The source
   apply check is distinct from a complete Firefox compile.
2. Add broker tests using controlled device discovery/ioctl fixtures: a linked
   AVD M2M video/media pair is admitted; an unrelated camera-only media node is
   denied; a controller naming only a non-admitted video is denied; non-video
   interfaces, regular files, symlink nodes, failed ioctls, zero/257 interfaces,
   count growth/shrinkage and version changes between queries all fail closed.
   Assert only the admitted video uevent is readable and no sysfs subtree is
   granted. Cover both single- and multiplanar M2M capability bits and the
   V4L2_CAP_DEVICE_CAPS fallback. Review device hot-unplug/replacement races:
   this remains path-based policy, like existing V4L2 admission, and is not
   a device-fd broker or dynamic hotplug permission mechanism.
3. Extend the existing RDD seccomp tests with the four exact ioctl constants.
   Verify an unrelated media ioctl is denied, unchanged 'V'/DRM/DMA-BUF behavior,
   and no '|' allowance when V4L2 is disabled. Exercise request-fd poll/mmap/close
   through the bridge. Do not broaden policy based on a guessed ioctl family.
4. On an authorized target, run the bridge `vainfo`, baseline Firefox and patched
   Firefox commands in [the qualification guide](../avd-userspace.md). Use muted
   H.264/HEVC/VP9 clips and AV1 only where present. Record `about:support` Media
   and Graphics sections, decoder logs, frame correctness, device
   fds and `Seccomp: 2` for RDD. Confirm the camera video/media pair stays denied.
   Repeat with stock GPU VA-API and software decode to detect regressions.
5. Revoke candidate use by closing the test profile and launching stock Firefox.
   Retain the stock package and all failing logs. No sandbox-disabling launch
   variable is part of this proposal. This patch needs Mozilla security review
   and target qualification before it can become a distro Firefox patch.

The patch and this test plan were AI-assisted. No independent reviewer or
hardware validation is implied. Chromium's device broker is outside this patch.
