# Updates: from a source branch to installed Macs

The cross-distribution overview, threat model and key procedures are in
[aurora-distributions/docs/updates.md](https://github.com/aurora-silicon/aurora-distributions/blob/main/docs/updates.md).
This page is the Fedora runbook; [RELEASING.md](../RELEASING.md) covers images, payloads and hardware
qualification.

## Installed systems

`images/configure.py` writes `/etc/yum.repos.d/aurora.repo` from `aurora-repos`'s own file, with
`baseurl=https://aurorasilicon.org/fedora-aurora/$releasever/<channel>/aarch64`, `gpgcheck=1`,
`gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-aurora` and `skip_if_unavailable=False`. `<channel>` comes
from the `images.yml` input; the default, `testing`, is today's URL. The `aurora-repos` package owns the
same repo file (testing channel, `%config(noreplace)`) and the key, and ships the dnf5 vendor change
policies in `/usr/share/dnf5/vendors.d/aurora*.conf`. `aurora-release` and `aurora-platform-core` require
it, so a Fedora Asahi Remix system that takes Aurora's platform packages gets the repository and the
policies together. An image built for another channel keeps its own baseurl in the config file.

The feed publishes only `44/`. dnf resolves `$releasever` for the release it is installing, so
`dnf system-upgrade download --releasever=45` asks for `45/` and stops with
`Failed to download metadata ... for repository "aurora"` until that tree exists. Otherwise dnf would
skip the repository, and with the `--allowerasing` it suggests, the upgrade removes `aurora-release` and
replaces Aurora's packages with Fedora's where it can. A refresh also fails when the site cannot be
reached, as with Fedora's own repositories. Upgrading before an Aurora tree exists takes an explicit
`--disablerepo=aurora`. A new Fedora release needs `<release>/<channel>/aarch64` published (the
producer scripts write `44/` today) and an `aurora-release` for it.

Packages are signature-checked; the repository metadata is not (`repo_gpgcheck=0`), although the feed
still signs it. Fedora 44's dnf5 trusts a metadata key only after a prompt, and a refresh that nobody
answers (the `dnf5-makecache` timer, `dnf` without a terminal, `dnf5 offline-upgrade`) skips the
repository and every Aurora update in it. The setting is a dnf5 repository override,
`/usr/share/dnf5/repos.override.d/50-aurora.repo`, so it also applies to a repo file that was changed
locally. Once Fedora's dnf5 has `auto_import_local_keys`, which the override already sets, the metadata
check can come back. The image imports the key into its rpm database (`config.sh` checks it), so the
first Aurora install does not ask either, and the image build checks every Aurora package against it
(`package_gpgcheck` in the KIWI repository). The build checks Fedora's packages the same way, against
the KIWI description's Fedora key (`distribution-gpg-keys`, the same key as `fedora-gpg-keys`), and
`configure.py` refuses an upstream repository that has no key.

Fedora Asahi Remix sets `allow_vendor_change=False`. Images built before `aurora-release` 44-7 have no
policies, so their first `dnf upgrade` brings the policies (`aurora-release` and `aurora-repos` carry no
vendor and upgrade without a vendor change) and the second one makes the vendor switches. Later images
switch in one go.

A kernel update runs `kernel-install`: dracut builds the initramfs (with `dracut-asahi` and
`98aurora-peripherals`, which read this Mac's firmware from the ESP at boot), and grubby adds the boot
entry. The `15-update-m1n1.install` plugin runs `update-m1n1` with the kernel version
being added or removed. It prepares the versioned DTB directory and changes `/boot/dtb` only after
validating the shared Stage 2 update. aura and U-Boot updates use the same updater through RPM file
triggers on `/usr/lib64/m1n1` and `/usr/share/uboot/apple_m1`.

## Device trees and the next boot

Device trees describe the Mac's hardware. They ship with the kernel, but the bootloader needs them
inside the ESP Stage 2 image to apply the firmware fixups before Linux starts. A kernel update therefore
also prepares a Stage 2 image containing the new device trees.

With aura Stage 1 version 1.0.0b4 or later, the updater leaves the working image in place. It writes
`<target>.next` beside it, reads it back, checks the DTB headers and this Mac's root compatible, and
checks that its display aliases are still present. It then writes the ESP root file `aura-try` with
exactly `armed\n<ESP-relative .next path>\n`. The marker is written through `aura-try.tmp`, synced and
renamed, then the filesystem and ESP block device are flushed. Stage 1 spends the marker on disk
before trying the candidate. A failed trial therefore boots the configured image on the next boot.
The updater reads the installed Stage 1 version from the live device tree, not from the aura RPM.
Older Stage 1 installations keep the direct atomic replacement and `<target>.old` backup.

On a trial boot, `aurora-stage2-commit.service` runs once after the system reaches `multi-user.target`.
It checks that the root filesystem is mounted on NVMe, no DT-described device remains in deferred
probe, and every enabled DCP has a bound driver. Debugfs must expose `devices_deferred` for that check.
The service also checks that the candidate still matches its recorded hash and that the booted trial
path names that candidate. It saves `<target>.prev`, atomically renames `.next` over the live image,
flushes the ESP, verifies the live image's SHA-256, and removes the marker. The backup remains available
for recovery. If a write or read-back fails, it restores the previous live image and keeps the candidate.

The trial retains Stage 1's watchdog fallback. A twelve-minute `aurora-stage2-guard.timer` also reboots
an uncommitted trial, covering a Linux boot that feeds the hardware watchdog but cannot pass the checks
or reach the commit service. It does nothing after a successful commit or on an ordinary boot.

If Stage 1 fell back, the commit service writes one journal line saying so, keeps the working image,
and leaves `.next` and `.next.json` for inspection. The updater records an attempt per selected kernel
version under `/var/lib/aurora-stage2/attempts` before arming the marker. Package triggers and later
boots never automatically try that version again. A later kernel version can get its own trial; the
previous candidate and receipt are kept beside the target as `.failed-<sha256>` files. An already
armed marker, another trial's marker, or a running trial prevents replacement of the candidate.

`journalctl -u aurora-stage2-commit -u aurora-stage2-guard` shows the outcome. After a failed trial,
inspect the retained candidate and receipt before making any manual recovery change. A new package
transaction does not remove a fallback kernel or reset its recorded trial attempt.

## DT ABI generations

`kernel-aurora-core` ships `/usr/lib/modules/<release>/dtb-abi`, an integer declaring the DT ABI
generation. Device trees can change within a generation while retained kernels remain compatible.
Only an incompatible ABI change needs a higher generation. An older package without the file counts
as generation zero; malformed declarations are refused.

The updater refuses a selected tree generation only when a retained kernel has a lower generation.
Equal and higher retained generations are allowed, even when the DTB bytes differ. It validates that
kernel images and device trees exist, including retained boot entries and rescue kernels. Custom
`DTBS` settings must match an installed tree set with a known generation. Refusal preserves the live
Stage 2 and `/boot/dtb`, lists the older kernels, and suggests an explicit removal command. First
verify a working compatible fallback. No fallback is deleted automatically, and failed erase-time
refreshes still allow the erased kernel's own boot files to be cleaned up.

## Checking updater changes

Run `scripts/test-stage2-transactions <proof-directory>` in a disposable Fedora 44 aarch64 container
on the buildbox. It builds the updater RPM and synthetic boot-input RPMs, exercises the real RPM
trigger and kernel-install hooks, and runs the updater tests against both source and the installed
helper. Those tests cover an armed trial without a commit, a successful trial commit, fallback,
the older Stage 1 path, generation refusal, DT checks and interrupted writes. The simulated proc/sys
trees never expose a host device. `scripts/test-bootchain-upgrade` retains the earlier transaction
checks using pinned historical input RPMs. Both paths require container isolation.

## CTXR Stage 2 slots

`update-m1n1` is Aurora's package (`packages/update-m1n1`). The `priority=1` repository and vendor
policies move an installed system to it, and `aura` requires its trial-aware version. The same generation
and trial checks apply to the CTXR slot described below.

The aura package ships `/usr/share/aura/monitor-free` once its pinned source has no monitor. `aura.spec`
declares that in `%global monitor_free`, and `%prep` refuses a source that disagrees (`src/ctxr_exec.c`, or
no `src/monitor.c`). aura 1.0.0b7 is the first pin without the monitor (aura#77), so `monitor_free` is 1. Macs that
don't boot a Mach-O Stage 1 keep updating `boot.bin`, using `.next` trials when Stage 1 supports them.

Such an aura moves the kernel into the CTXR window, which only a kernel built with
`CONFIG_ARM64_CTXR_EXECMEM` keeps its code inside. With `monitor_free` 1, aura requires
`aurora-ctxr-execmem`, which `kernel-aurora-core` provides when `kernel-aurora.spec` sets `ctxr_execmem` 1.
Its `%build` checks that against the resolved configuration, so it can be set only with a kernel pin that
has aurora-silicon/linux#985. `tests/test_update_m1n1.py` fails if `monitor_free` is set without it.
RPM checks this per package, not per boot: `kernel-aurora` is install-only, so any installed
`kernel-aurora-core` that provides `aurora-ctxr-execmem` satisfies aura, while older kernels without it stay
installed and in the GRUB menu. Booting one of those with an aura that has no monitor would hit the faults
this rule exists for, until dnf removes it as the install-only limit rotates kernels out.
Every kernel pin since 4731456 has it, and `packages/kernel-aurora/config` turns it on, so `ctxr_execmem` is 1.

With the marker, a Mac that boots a Mach-O Stage 1 (`/proc/device-tree/compatible` names one of the chips
in the installer's `AuraStage1Format.usesMachO`: T8130 and later, T6040 and later) gets
`m1n1/boot-ctxr.bin` instead, with only this board's DTBs. A trial uses `boot-ctxr.bin.next` and a `.prev`
backup on commit; older Stage 1 uses direct replacement and `.old`. It leaves `boot.bin` untouched,
because the padded Stage 1 these Macs enroll chainloads `boot-ctxr.bin`. Earlier chips continue to
target `boot.bin`. Missing board trees and candidates above the 16 MiB
CTXR slot limit are refused before either live image or the boot link changes.

Image builds set `AURORA_DEVICE_TREE_COMPATIBLE=/nonexistent`, so `update-m1n1` writes `boot.bin` as before
whichever Mac builds the image. If the image's aura has the marker, `scripts/prepare-ctxr-stage2.py` then
adds `boot-ctxr.bin`, a copy of it, to the image's ESP, and `boot-ctxr-<board>.bin`, a copy of
`boot-<board>.bin`, for each Mach-O board. The installer picks the board's file over the combined one. The
script fails the image if any of them is over 16 MiB. Without the marker the image has no `boot-ctxr.bin`,
and the installer refuses it on Mach-O Macs, so no Mac gets a `boot-ctxr.bin` that updates don't refresh.

## Repository metadata check

`repo_gpgcheck` stays off until Fedora ships a dnf5 with `auto_import_local_keys` (upstream e2e9b949 and
04683e76, October 2026; Fedora 44 and 45 have 5.4.6, and no release has it yet). dnf5 5.4.6 offers no
clean way to trust the metadata key without asking:

- **Pre-seeding the keyring.** dnf5 keeps the key in `<cachedir>/<repoid>-<hash>/pubring`, where the
  hash comes from the resolved baseurl. `dnf clean all` leaves it, because it removes the cache directory
  only once it is empty. But only dnf itself can seed it without writing librepo's key files by hand, and
  only with `-y`, and every new URL starts empty: a release upgrade, a channel switch, and each cache
  (root's, every user's, PackageKit's, dnf5daemon's). Seeding from the image build or a drop-in for
  `dnf5-makecache.service` would leave a window after each of these in which every non-interactive
  refresh fails (`skip_if_unavailable=False`).
- **An option.** `assumeyes` is the only setting the command line's key callback reads, and in
  `dnf.conf` it would also answer every transaction prompt.
- **Carrying the upstream change.** The six upstream commits cherry-pick onto 5.4.6.0 without conflicts
  and only add to the library's API. But an Aurora dnf5 in the `priority=1` repository would hide every
  later Fedora dnf5 update until Aurora rebuilt it (Fedora shipped 5.4.5 and 5.4.6 ten days apart),
  nothing here tracks Fedora's packages, every system with the repository, Fedora Asahi Remix included,
  would have to take Aurora's package manager, and a Fedora dnf5 without the option would bring the prompt
  back.

When a Fedora dnf5 with the option reaches Fedora 44, the steps below are enough. They were tried with a
scratch build of 5.4.6.0 plus those commits: refreshes without a terminal, after `dnf clean all` and with
the keyring deleted imported the key without asking, and so did PackageKit.

1. In `packages/aurora-repos/aurora-override.repo`, set `repo_gpgcheck=1` and keep
   `auto_import_local_keys=1`. The key stays at `file:///etc/pki/rpm-gpg/RPM-GPG-KEY-aurora`, inside
   the directories the option trusts, spelled as it requires.
2. In `aurora-repos.spec`, add `Requires: libdnf5 >= <that version>`, so no system has the check
   without the option, and bump the release.
3. Leave the KIWI Aurora repository at `package_gpgcheck`: KIWI writes no `gpgkey` into its repository
   files, so it has no key to import for the metadata.
4. Update the tests: `tests/test_specs.py` expects the override, and `scripts/test-repo-trust` already
   runs every refresh with the metadata check when the installed dnf5 has the option.

## Workflows

| Workflow | Trigger | Does |
|---|---|---|
| `track-sources.yml` | every 30 min (`TRACK_SOURCES`), manual | Moves `aura`, `kernel-aurora`, `mesa-aurora` to their branch tips in one PR (spec `%global commit`, `Version`, `Release`, `%changelog`), dispatches `rpms.yml` and `checks.yml`, merges when green (`AUTO_MERGE_SOURCES`), mirrors archives to `source-cache` |
| `rpms.yml` | push, PR, manual | Native RPM builds; attests every RPM |
| `publish.yml` | after a main build and every 6 h (`AUTO_PUBLISH_TESTING`), manual | Newest qualifying build per package, merged with the newest snapshot, version-checked, signed in `testing-signing`, released with an attestation. **It no longer deploys by itself**: it deploys only with `AUTO_DEPLOY_TESTING` or `deploy=yes` |
| `deploy-snapshot.yml` | manual or called | Serves a snapshot's signed metadata on `testing` or `stable` (both channels are rebuilt into one Pages site), verifies signatures, attestation and the live repository's versions, records `channels.json` |
| `promote.yml` | manual | `stable` gets what `testing` serves, after a `stable-promotion` reviewer approves |
| `images.yml` | manual or after a testing deploy (`AUTO_IMAGES`) | Builds an image; `channel` sets its repository URL |
| `payload-after-images.yml` | after an image build (`AUTO_PAYLOADS`) | Signed payload release; catalog adoption stays manual |

## Common tasks

```sh
gh workflow run publish.yml -R aurora-silicon/fedora-aurora --ref main -f dry-run=true
gh workflow run publish.yml -R aurora-silicon/fedora-aurora --ref main -f deploy=yes
gh workflow run deploy-snapshot.yml -R aurora-silicon/fedora-aurora --ref main -f channel=testing -f release-tag=testing-YYYYMMDD.N
gh workflow run promote.yml -R aurora-silicon/fedora-aurora --ref main
```

`publish.yml -f build-run='<ids>' -f base-release=<tag> -f release-tag=<tag>` still works, and now needs
`-f deploy=yes` to go live as it used to.

## Notes

- Changing `rpms.yml`, `scripts/build-rpm`, `scripts/fetch-sources.py` or `scripts/build-receipt.py`
  makes every earlier build ineligible; the next publication requests a full main build first.
- Source archives come from the `source-cache` release when present (set `AURORA_SOURCE_MIRROR=` to skip
  it); every byte is checked against `sources.json` either way.
- Images still build against the live testing feed rather than a frozen snapshot; freeze publication
  while building a release set.
