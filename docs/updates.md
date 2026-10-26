# Updates: from a source branch to installed Macs

The cross-distribution overview, threat model and key procedures are in
[aurora-distributions/docs/updates.md](https://github.com/aurora-silicon/aurora-distributions/blob/main/docs/updates.md).
This page is the Fedora runbook; [RELEASING.md](../RELEASING.md) covers images, payloads and hardware
qualification.

## Installed systems

`images/configure.py` writes `/etc/yum.repos.d/aurora.repo` with
`baseurl=https://aurorasilicon.org/fedora-aurora/44/<channel>/aarch64`, `gpgcheck=1`, `repo_gpgcheck=1`
and `gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-aurora`. `<channel>` comes from the `images.yml` input;
the default, `testing`, is today's URL. No package owns the repo file or the key yet, which blocks key
rotation (see the overview).

A kernel update runs `kernel-install`: dracut builds the initramfs (with `dracut-asahi` and
`98aurora-peripherals`, which read this Mac's firmware from the ESP at boot), grubby adds the boot entry
and `/boot/dtb` link, and the `15-update-m1n1.install` plugin rewrites the ESP Stage 2. aura and U-Boot
updates trigger `update-m1n1` through RPM file triggers on `/usr/lib64/m1n1` and
`/usr/share/uboot/apple_m1`.

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

The kernel prepares the pinned, corrected bindgen at
`tools/aurora-bindgen/build/bin/bindgen` before configuration. Kbuild selects it
automatically, including out-of-tree builds. No `BINDGEN=` make argument or
export is required. Fedora and ALARM build and compile-test the generator from
the kernel's checked source manifest; Nix uses the matching patched derivation
and links its executable into that entry point. ALARM retains its exact
compiler-lint adapter there. Every emitted layout assertion remains mandatory.
Stock bindgen 0.73.2 loses alignment on empty C records such as
`sched_statistics` with `SCHEDSTATS=n`; enabling statistics is not the fix.

Cons3 also pins FAT's default codepage 437 and ASCII charset, with both
converters built into the kernel. Asahi's early dracut vendor-firmware hook
mounts the ESP without charset options; it must not depend on a charset module
missing from initramfs. XZ and Zstd firmware loading are enabled for compressed
distribution firmware files. The shared fragment carries these requirements.
