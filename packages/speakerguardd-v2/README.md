# speakerguardd-v2

speakerguardd 1.0 (`1.0.0-alpha`), the in-graph speaker protection from
aurora-silicon/speakerguardd. It is a new program, not an upgrade of the 0.1
daemon, so it is packaged under its own name.

## The only speaker stack

speakerguardd v2 is the only speaker protection on every Mac, and the only
program that takes the kernel's speaker interlock. aurora-audio (which every
install has) and aurora-platform require it; aurora-audio obsoletes
speakersafetyd, speakersafetyd-aurora-profiles, speakerguardd 0.1 and
asahi-audio, so an upgrade removes them, and installs no Asahi speaker graph.

At every boot the gate (`speakerguardd-gate`, the `ExecCondition=` of the
supervisor and its sleep hook) starts v2 on a board whose protection unit is
at parity and qualified, when the kernel has the v2 interface (the "Speaker
Protection" control). A board outside the gate runs no speaker daemon, and
the kernel holds its speakers at its floor. The gate's data is
speakerguardd's own (`/usr/share/speakerguardd/gate.json`: the units at
parity and the qualified boards per unit), so it is the same in every
distribution and never edited here. Nothing about a board is entered by
hand: the protection unit is the one the Mac's own tuning names, and the
channel map, card, amplifiers and sense lanes are derived from its device
tree and tuning at run time (`wiring.py`), so a new Mac needs no table entry.

`speakerguardd-gate explain` (beside the supervisor) prints the decision.
For qualification itself, an administrator can name an unqualified board in
`/etc/speakerguardd/allow-unqualified`.

## No manual steps

On a gated board, `speakerguardd-v2-provision.service` runs before the
self-check and the supervisor, which both require it:

- it compiles the installer's tuning bundle (`/lib/firmware/vendor/apple/audio-tuning`,
  or the ESP's vendorfw archive) into `/var/lib/speakerguardd/params.bin`;
- it binds the blob to the board, kernel, bundle, macOS build and compiler,
  and recompiles when one changes;
- it resolves the seat user by name, never by a fixed uid;
- it writes `/etc/speakerguardd/speakerguardd.conf`.

After the self-check passes, the machine's PipeWire and WirePlumber files are
generated into `/run/speakerguardd-graph`. The user unit
`speakerguardd-v2-graph.service` links them for the seat user only.
`speakerguardd-v2-seat.path` provisions again when another user takes
seat0. Any failure fails closed: the supervisor does not start, the kernel's
floor holds, and the journal says why.

Overrides, all optional, go in `/etc/speakerguardd/provision.conf`:
`SGV2_SEAT_USER=<name>` and `SGV2_BUNDLE=<path>`.

## What it installs

| Path | What |
|---|---|
| `speakerguardd-v2/` under `/usr/libexec` (Fedora), `/usr/lib` (Arch) or `libexec` (Nix) | The supervisor, `speakerguardd-provision`, `speakerguardd-gate`, `speakerguardd-selfcheck`, `speakerguardd-session` |
| `speakerguardd-v2{,-provision,-selfcheck,-seat}.service`, `speakerguardd-v2-seat.path` | The upstream units, renamed and enabled, each one gated |
| `speakerguardd-v2-session.service`, `speakerguardd-v2-graph.service` (user units) | The session helper, and the seat user's graph links |
| `sgv2.lv2` in the distribution's LV2 directory | The protection unit for the PipeWire filter-chain |
| `aurora-speaker-tuning` | Reader, validator and compiler for the Mac's own tuning bundle |
| `/usr/share/speakerguardd/` | `gate.json` and the reference graphs |
| SELinux module `speakerguardd` (Fedora) | Upstream's policy: `speakerguardd_t`, with the program, `/run/speakerguardd` and `/var/lib/speakerguardd` labelled |

## Turning it off

`systemctl disable speakerguardd-v2.service` (NixOS:
`aurora.speakerguardd.v2.enable = false;`) leaves the speakers at the
kernel's floor. There is no other speaker stack to fall back to.

## Source

The pin is a commit on speakerguardd's `main` branch. Bump it as changes merge there.
`aurora-speaker-tuning` is based on aurora-audio-dsp by saku (MIT); its
notice is installed with the licence.
