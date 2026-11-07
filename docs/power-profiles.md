# Power profiles on Apple Silicon

Fedora uses tuned-ppd. Its stock GNOME Performance mapping selects
`throughput-performance`, whose CPU governor is `performance`. On a Neo,
Fedora 45, AC, settled desktop, 120 seconds per idle sample:

| Profile | Idle power | Single-thread count | All-thread count |
| --- | ---: | ---: | ---: |
| balanced | 3476 mW | 2615 | 7152 |
| powersave | 3475 mW | 2648 | 7059 |
| throughput-performance | 4953 mW | 2668 | 6881 |
| balanced (repeat) | 3493 mW | 2747 | 7138 |

Counts are 20-second integer-loop iterations, not stress-ng scores. Stock
Performance cost 1477 mW (1.48 W, 42%) at idle with no measured throughput
gain. These are baseline observations, not measurements of this fix.

## Fedora policy and configuration ownership

`aurora-platform-core` ships
`/usr/lib/tuned/profiles/aurora-performance/tuned.conf`. It inherits the
non-CPU tuning from `throughput-performance` and **replaces** the CPU section
with `governor=schedutil`. This removes inherited `boost=1` and
`min_perf_pct=100`; merely omitting a boost line would still inherit it.
The kernel retains boost policy. Per-policy boost writes from stock tuned
profiles fail with EINVAL on M2; this profile makes no such writes.

A small helper changes only the exact stock
`performance=throughput-performance` line in `[profiles]` to
`performance=aurora-performance`. Other settings, comments, battery overrides,
custom performance mappings, malformed files and administrator symlinks are
left alone. A migration that would make a custom AC or battery mapping
ambiguous is also skipped: tuned-ppd requires one-to-one mappings.
It retains the first original in `ppd.conf.aurora-original` and
preserves file ownership, permissions and extended attributes on replacement.
An active tuned-ppd is restarted after a change to consume the mapping and
reapply its saved base profile; an inactive service is not started. Temporary
profile holds can be released by this restart.

The helper runs in core's `%posttrans` and a `%transfiletriggerin` on
`/etc/tuned/` (RPM indexes transaction triggers by directory prefix), covering
a later tuned-ppd install or upgrade without
requiring an Aurora package update. tuned-ppd keeps sole RPM ownership of its
`%config(noreplace)` file. Existing local edits therefore retain RPM's normal
`.rpmnew` handling, and a custom mapping stays custom. This is preferable to
a downstream tuned fork: no daemon patch or competing config owner is needed.
If upstream changes its stock line or config format, the helper leaves it for
review rather than guessing. Aurora package installation scopes this policy
to Aurora systems; the RPM does not alter upstream tuned profiles.

## Power Saver

Power Saver gets a CPU power budget from `aurora-power-budget`, built from
[aurora-platform](https://github.com/aurora-silicon/aurora-platform/blob/main/power/README.md)
and packaged here as the `aurora-power-budget` subpackage (enabled by preset, required by `aurora-platform-core`). Like macOS Low Power Mode it is a short-window
budget, not a fixed frequency table: while the profile daemon reports
`power-saver`, every 100 ms the budget (the device tree energy model's power
for every CPU at 0.6 x its cluster maximum) is spent on the frequency steps
that buy the most CPU capacity per milliwatt, and each cluster is capped with
`scaling_max_freq`. Thermal limits still win; the governor stays `schedutil`;
light and single-threaded work is not capped. Balanced and Performance are
untouched, and outside Power Saver the daemon only waits on D-Bus. The GPU,
ANE, display and fan legs of Low Power Mode are not covered yet. Measurements
are in the aurora-platform README.

## Distribution parity

ALARM and NixOS use power-profiles-daemon rather than tuned-ppd. Its current
Apple path has no Apple CPU/platform-profile driver. The placeholder path
provides no equivalent CPU performance tuning and does not pin CPU clocks.
Available profile names alone do not prove hardware control; other generic
PPD actions may still apply. Neither distribution needs the Fedora mapping
migration or a performance governor override. See their `docs/power-profiles.md`.

## PWR qualification before merge

1. Record kernel/package versions, AC state, temperature, brightness and the
   existing profile. Install the candidate RPM. Confirm `rpm -qlp` lists the
   profile and `tuned-adm list` finds `aurora-performance`.
2. Select Balanced, Power Saver, Performance, then Balanced again through
   `powerprofilesctl`. Record `tuned-adm active`, each policy's governor,
   scaling min/max, current frequency and global/per-policy boost values.
   Performance must select `aurora-performance` and `schedutil`; CPU frequency
   must fall at idle. Check the tuned journal for failed boost writes.
3. On the Neo, repeat matched, settled 120-second idle-power samples for each
   profile in at least two passes. Keep background workload, AC state and
   brightness consistent. Compare Performance with Balanced and the baseline
   above; do not claim a saving from a config-only check.
4. Run the same stress-ng version with `--cpu 1 --cpu-method int64 --timeout
   60s --metrics-brief` and then `--cpu 0` for each profile. Repeat to establish
   variation; record bogo-ops/s, clocks, temperatures and throttling. Require
   no repeatable Performance throughput regression relative to Balanced.
5. On M2, confirm Performance makes no boost writes and preserves the kernel
   boost setting. On ALARM/NixOS, record the reported PPD driver and available
   profiles, and confirm selecting supported profiles does not introduce a
   performance governor or a new frequency floor.
6. Exercise fresh install, tuned-ppd-only upgrade/reinstall and a custom
   performance mapping. Verify other config bytes survive and custom mappings
   remain selected. PWR owns device qualification and merging; these PRs are
   intentionally left unmerged.

Rollback: select Balanced, then change only the migrated `[profiles]` line
back to its previous mapping and restart an already active tuned-ppd. Keep
later administrator edits; inspect the backup rather than blindly restoring
it. Downgrade/remove the candidate Aurora package before reinstalling a stock
mapping, otherwise its transaction trigger will migrate that stock line again.

Public implementation references:
[TuneD throughput-performance](https://github.com/redhat-performance/tuned/blob/master/profiles/throughput-performance/tuned.conf),
[TuneD profile merger](https://github.com/redhat-performance/tuned/blob/master/tuned/profiles/merger.py),
[tuned-ppd configuration](https://github.com/redhat-performance/tuned/blob/master/tuned/ppd/ppd.conf).
