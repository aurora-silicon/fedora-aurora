# Plymouth terminal input carry

This carries Fedora 45's Plymouth 26.134.222 recipe with a nonblocking
terminal input fix. Fedora's subpackage names and existing patches are
retained. Build with `scripts/build-rpm plymouth` on Fedora aarch64.

The terminal open path requests `O_NONBLOCK` and then clears it. Both the
event-loop readiness notification and `ply_buffer_append_from_fd()`'s poll
can become stale before the subsequent read. Reading from the separate
nonblocking input descriptor lets the handler return when that happens.
The buffer helper already ignores `EAGAIN` without appending data.
The existing descriptor remains blocking for output, including direct
writes from the text display. Reasserting raw mode alone would still
leave a race between changing termios and reading.

`0001-ply-terminal-Keep-terminal-input-nonblocking.patch` contains the
production change. `test-terminal-input.c` is the same PTY regression
submitted with the upstream patch. The release predates upstream's Meson
test harness, so `%check` builds it against the newly built libraries.
It covers empty input, input consumed after readiness, a console reset
between readiness and reading, a partial canonical line, a subsequent
complete line, and close/reopen cleanup. It requires no physical console.

## Source provenance

- [Fedora 45 packaging, commit 790078d](https://src.fedoraproject.org/rpms/plymouth/tree/790078d)
  provides the spec, charge theme descriptor and two existing patches.
  The carry replaces autorelease 6 with `6%{?dist}.aurora1`.
- [Plymouth 26.134.222](https://gitlab.freedesktop.org/plymouth/plymouth/-/tree/1aacf818fd5d1b6a7695546eb08fcbc46893dd0b)
  is pinned by commit and archive SHA-256 in `sources.json`. The archive
  also matches Fedora's published SHA-512.
- [Terminal open and raw-mode handling](https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/1aacf818fd5d1b6a7695546eb08fcbc46893dd0b/src/libply-splash-core/ply-terminal.c),
  [keyboard reads](https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/1aacf818fd5d1b6a7695546eb08fcbc46893dd0b/src/libply-splash-core/ply-keyboard.c),
  and [buffer reads](https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/1aacf818fd5d1b6a7695546eb08fcbc46893dd0b/src/libply/ply-buffer.c)
  define the affected path. The sources are GPL-2.0-or-later.

## Splash start ordering

`0001-systemd-units-Start-plymouthd-without-waiting-for-coldplug.patch`
orders `plymouth-start.service` after `systemd-udevd.service` and
`dracut-pre-trigger.service` instead of `systemd-udev-trigger.service`.
A systemd drop-in cannot do this: drop-ins can add ordering dependencies
but cannot remove one. The `systemd-udev-trigger.service` ordering dates
from plymouth commit aaad73c3, when plymouthd read an empty udev queue as
"coldplug complete". Plymouth 26's device manager no longer reads the
queue. It adds renderers from udev add events and falls back after
`DeviceTimeout`. With aurora-platform's `91aurora-early-kms`, which
coldplugs the display in dracut's pre-trigger hook, a J700 draws the
splash at 3.0 s instead of 3.65 s.

## Equivalent distribution carries

ALARM: add a `packages/plymouth/PKGBUILD` carry of the distribution recipe,
retain its existing patches, add this production patch and checksum to
`source`/`sha256sums`, apply it in `prepare()`, bump `pkgrel`, and run this
PTY regression in `check()` against the built libraries. Rebuild the
initramfs with the distribution's existing mechanism after installation.

NixOS: add the production patch to `prev.plymouth.overrideAttrs` in
`overlay.nix`, appending to `(old.patches or [])`. Keep the upstream source
version, enable the PTY regression in `postCheck`, and use the resulting
package for `boot.plymouth.package`. Rebuild the boot generation so its
initrd contains the patched libraries. These are porting notes; this
branch changes only the Fedora carry.

Retire the carry once the distribution package includes an upstream
fix that guarantees nonblocking terminal keyboard reads.
