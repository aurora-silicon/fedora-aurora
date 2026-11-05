# Plymouth terminal input carry

This carries Plymouth 26.134.222 on Fedora 44 and Fedora 45
with nonblocking terminal input and script keyboard lifetime fixes. Fedora's subpackage names and existing patches are
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
  Both Fedora 44 and Fedora 45 build it as `6%{?dist}.aurora4`. Fedora 44
  must not go back to 24.004.60: the published Fedora 44 repository already
  carries 26.134.222-6, and an older build would never install on update.
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

ALARM and NixOS carry the same terminal and keyboard-lifetime patches in
one Plymouth recipe each. They run the PTY regression and native lifecycle
fixtures against their built libraries and require the lifetime capability
from theme 1-4. Rebuild the distribution's initramfs after installation.

Retire the carry once the distribution package includes an upstream
fix that guarantees nonblocking terminal keyboard reads.

## Script splash renderer removal

The carry also fixes keyboard lifetime during renderer removal on Fedora 44
and 45, both on 26.134.222. See
[KEYBOARD-LIFETIME.md](KEYBOARD-LIFETIME.md) for the cause, source provenance,
regression checks, package dependency, and rollback requirements.
