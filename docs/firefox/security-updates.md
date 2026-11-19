# Firefox security updates

Aurora's Firefox is Fedora's package plus the RDD V4L2 Request decoder patch
([README](README.md)). The Aurora repository has `priority=1`, so dnf takes
Firefox only from Aurora and never offers Fedora's build, even when Fedora's
is newer. A Fedora Firefox security fix therefore reaches Aurora systems only
once Aurora's rebuild is served. This document sets the deadline for that
rebuild and what happens when it is missed.

## Trigger

A Fedora Firefox update of type `security` for Fedora 44 or Fedora 45, as
recorded in [Bodhi](https://bodhi.fedoraproject.org/updates/?packages=firefox&type=security).
The clock starts when Fedora first pushes it, to `updates-testing` or straight
to `updates`, whichever comes first. An update Fedora unpushes or revokes ends
the obligation. Bugfix and enhancement updates have no deadline; the tracker
still rebuilds them.

## Deadlines

| Aurora channel | Due after Fedora's push |
|---|---|
| testing (Fedora 44 and 45) | 72 hours |
| stable (Fedora 44 only; Fedora 45 is testing-only) | 7 days |

The deadline covers `firefox` and the matching `firefox-langpacks`, built
from the same source package. Each Fedora release has its own Bodhi update
and its own deadline.

Severity is Bodhi's. `urgent` (critical) and `high` updates keep the same
deadlines but escalate at 48 hours if testing is still behind. Others
escalate when a deadline passes.

## Owners

- Accountable: the distro merge-train maintainers.
- Backup: the release coordinator, who takes over when the maintainers have
  not acted by the escalation point.

The repository variable `FIREFOX_SLA_MENTION` (a team or user handle) is
mentioned in escalation and overdue comments.

## Meeting the deadline

A rebuild is "served" only after every step below is done for both Fedora
releases:

1. **Import.** `track-firefox.yml` imports Fedora's f44/f45 dist-git heads
   every two hours with `scripts/import-fedora-firefox.py`. Fedora's files are
   kept byte for byte; the lookaside archives are fetched by their SHA-512
   from `sources` and the API key files by the SHA-256 in `distgit.json`.
2. **Build and test.** The proposal branch `auto/firefox-<version>-<f44>-<f45>`
   builds Firefox and its langpacks for both releases (`rpms.yml`) and runs
   the source checks (`checks.yml`, including `tests/test_firefox.py`).
3. **Publish.** A passing proposal is merged and `publish.yml` signs the
   packages and the repository index and deploys the testing channel.
   Promoting to stable is `promote.yml`.
4. **Verify.** The deadline is met only when the served channel's metadata
   says so (see Freshness), not when a build or merge succeeds.

If the proposal build fails (for example a Fedora toolchain change breaks the
decoder patch or the build), fix it on the proposal branch or on main before
the escalation point. If it cannot be fixed in time, publish the fallback
below in the tracking issue and in the release notes before the deadline,
and keep working on the rebuild.

## Freshness

`scripts/check-firefox-security.py`, run by the `security-sla` job in
`track-firefox.yml` every two hours, checks each Fedora release:

- it reads Fedora's Firefox security updates from Bodhi, both `testing` and
  `stable` (and `obsolete` ones that were pushed);
- it reads `firefox` and `firefox-langpacks` from the primary metadata each
  Aurora channel serves (`https://aurorasilicon.org/fedora-aurora/<release>/<channel>/aarch64`);
- a channel is current for an update when its `firefox`, with the Aurora
  release suffix (`.auroraN`) removed, is at least Fedora's version-release,
  and `firefox-langpacks` is the same build. Comparing Fedora's full release,
  not only the upstream version, catches Fedora security rebuilds that add
  patches to the same upstream version. A higher `.auroraN` suffix alone
  never makes Aurora current: `160.0-1.fc44.aurora9` is behind Fedora's
  `160.0-2.fc44`;
- a channel the site does not serve yet (stable before its first promotion)
  is reported as such and not held to a deadline.

While Aurora is behind an update it keeps one GitHub issue for it, labelled
`firefox-security`, titled with the Fedora build and the testing deadline,
with both due times and each channel's state in its body. It comments once
when an urgent/high update reaches 48 hours, labels the issue `overdue` and
comments once per channel whose deadline has passed, and fails the workflow
run while anything is overdue. It closes the issue once every channel is
current, reopens it if a channel falls behind again, and closes it when
Fedora withdraws the update. Re-running it changes nothing. Set the
repository variable `FIREFOX_SECURITY_SLA=false` to stop it changing issues.

To check by hand (prints the plan, changes nothing):

```sh
python3 scripts/check-firefox-security.py
```

This is separate from the snapshot presence check added in
[#413](https://github.com/aurora-silicon/fedora-aurora/pull/413):
`REQUIRED_TOGETHER` in `scripts/assemble-repository.py` refuses a snapshot
that lacks Aurora's `firefox` and `firefox-langpacks`. That check knows
nothing about Fedora's updates; this one does not check snapshots before
they are published.

## Fallback: Fedora's stock Firefox

When Aurora's rebuild will miss its deadline, users can switch to Fedora's
updated Firefox by hand. The only loss is Aurora's decoder patch: video falls
back from the hardware V4L2 Request (AVD) decoder to software decoding.
Everything else, including profiles, is unchanged. This is manual on
purpose; nothing in the Aurora packages switches it automatically.

```sh
# Ignore Aurora's Firefox, then take Fedora's.
sudo dnf config-manager setopt aurora.excludepkgs=firefox,firefox-langpacks
sudo dnf distro-sync --refresh firefox firefox-langpacks
```

Once Aurora serves the rebuild (the tracking issue closes), go back:

```sh
sudo dnf config-manager unsetopt aurora.excludepkgs
sudo dnf distro-sync --refresh firefox firefox-langpacks
```

`dnf config-manager` comes from `dnf5-plugins`. If you already set `aurora.excludepkgs` for something else, add Firefox to
your list rather than replacing it. Fedora and Aurora are equivalent vendors
in Aurora's dnf configuration, so dnf swaps between the two builds without
asking.
