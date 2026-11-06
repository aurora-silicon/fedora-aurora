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
`98aurora-peripherals`, which read this Mac's firmware from the ESP at boot), grubby adds the boot entry
and `/boot/dtb` link, and the `15-update-m1n1.install` plugin rewrites the ESP Stage 2. aura and U-Boot
updates trigger `update-m1n1` through RPM file triggers on `/usr/lib64/m1n1` and
`/usr/share/uboot/apple_m1`.

`update-m1n1` is Aurora's package (`packages/update-m1n1`), Fedora's script with the change below; the
`priority=1` repository and the vendor policies move an installed system to it, and `aura` requires it.
On a Mac that boots a Mach-O Stage 1 (`/proc/device-tree/compatible` names one of the chips in the
installer's `AuraStage1Format.usesMachO`: T8130 and later, T6040 and later), it writes
`m1n1/boot-ctxr.bin` instead of `m1n1/boot.bin`, keeping `boot-ctxr.bin.old`, with only this board's
DTBs. It never touches `m1n1/boot.bin`: a Stage 1 with the CTXR window chainloads `boot-ctxr.bin`, and an
older one keeps chainloading its frozen `boot.bin`, because it can't run an aura without the monitor. A
frozen `boot.bin` also keeps its device trees, so such a Mac runs new kernels on old trees until it is
re-enrolled. M1 to M3 Macs only ever use `boot.bin`.

Without a device tree to read, as in an image build, `update-m1n1` writes `boot.bin` as before.
`scripts/prepare-ctxr-stage2.py` then adds `boot-ctxr.bin`, a copy of it, to the image's ESP, and
`boot-ctxr-<board>.bin`, a copy of `boot-<board>.bin`, for each Mach-O board. The installer picks the
board's file over the combined one.

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
