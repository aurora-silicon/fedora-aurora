# Native Fedora 45 Touch ID v5 packages

The `Touch ID Fedora 45` workflow builds `aurora-sep`, `libfprint` and `fprintd`
natively on arm64 in Fedora 45 containers. The existing Fedora 44 RPM workflow
continues to build these recipes for Fedora 44. The driver and daemon patches
are the same v4/v5 implementation shipped by #73; this changes packaging and
upgrade ordering only.

| Package family (including matching subpackages) | Fedora 45 EVR | Previous fc44 v5 EVR |
| --- | --- | --- |
| aurora-sep, aurora-sep-selinux | `0:1-16.fc45` | `0:1-15.fc44` |
| libfprint, libfprint-selinux, libfprint-devel, libfprint-tests | `1:1.94.100-1.fc45.aurora7` | `0:1.94.100-1.fc44.aurora7` |
| fprintd, fprintd-pam, fprintd-devel | `1:1.94.5-99.fc45.aurora1` | `0:1.94.5-99.fc44.aurora1` |

Epoch 1 keeps both patched upstream packages ahead of stock Fedora packages,
even when Fedora has a higher release number. Matching dependencies include
the epoch, including the conditional libfprint SELinux dependency. The existing
`libfprint(aurora-sep) = 5` and `fprintd(aurora-sep) = 1` capability requirements
remain in force. The epoch applies to Fedora 44 builds too, avoiding different
ordering rules between distro releases; future Aurora releases must retain it.

## Upgrade proof

`bash scripts/test-touchid-upgrade CANDIDATE_RPMS stock|FC44_RPMS` runs only as
root inside a disposable Fedora 45 container. The workflow runs it twice with
independent RPM databases:

1. Against the current stock Fedora 45 libfprint/fprintd packages, including
   their development and test subpackages.
2. Against all nine fc44 Aurora v5 packages rebuilt in Fedora 44 from immutable
   #73 source revision `09dec299bf0bd35d1990038e9b10c75f3dea253f`, the source of
   run `41147200126`. Rebuilding avoids depending on expiring CI artifacts.

The test logs the baseline NEVRAs, checks every candidate with RPM's EVR
comparison, and requires DNF `repoquery --upgrades` to identify every installed
component. It then runs a normal DNF `upgrade` against a local repository,
checks exact resulting NEVRAs and v5 capabilities, and verifies synthetic
fingerprint and SEP state files survive. On the stock path only the additional
Aurora packages are newly installed. Targeted SELinux policy is present, so
both policy subpackages are exercised even though the container has no reader
and does not run an enforcing SELinux host.

Both paths also exercise explicit rollback: stock-repository `distro-sync`
after removing the Aurora-only integration/policy packages, or `dnf downgrade`
to the exact fc44 baseline RPMs. Exact original NEVRAs and the synthetic state
files must survive the rollback. The container never accesses SEP hardware or
real enrolments. Runtime biometric qualification remains separate.

The `touchid-fedora45` artifact contains candidate binary/source RPMs, build
receipts, libfprint Meson logs, and both upgrade/rollback logs. These are unsigned
review builds. Publication, versionlock changes and target installation are
separate lead actions. Before a target change, retain its existing RPMs and
versionlock configuration; an epoch rollback requires an explicit downgrade or
selection of the intended stock repositories. Do not remove biometric state.

## Source parity

Compared Fedora main `86ff62cdf3091e98d8c7ab025ec64f3b5d19d7e2`, Arch Linux ARM
main `42bd1c5bfddb71577e140175a84eaa9481ba5b5f`, and NixOS main
`459d99d25dc1ccb484f30be2731cc397b10477c7`, plus this Fedora packaging change.

| Component | Fedora | Arch Linux ARM | NixOS |
| --- | --- | --- | --- |
| SEP helper provenance (`linux/tools/aurora-sep`) | `7cc30f35ecea3e90ceedd44babbde128c1d487a6` | same | same |
| libfprint base, 1.94.100 | `80a4b5ec612892c5c056c48dddaa561452cf37ec` | same | same |
| libfprint archive SHA-256 | `94ff7f3689d14da28389a4d9cad5fb523065bbed3e6c8e3694522fde1316e780` | same | same |
| v5 libfprint patches, UAPI header and compatibility test provenance | `aurora-sep-userspace@2799b51243708d0a551b67d902472319f132c417` | same | same |
| fprintd base | 1.94.5, `b54a007ccf58ac0ae074c7151b223f35cbd17306` | same v1.94.5 archive | v1.94.5 through locked nixpkgs |
| fprintd account/deletion patch and test provenance | `aurora-sep-userspace@2799b51243708d0a551b67d902472319f132c417` | same | same |

All seven shared libfprint patch/header/test files and both fprintd patch/test
files are byte-identical across the three distros. Fedora's fprintd provenance
previously named `86f67308110cbd414fb491e246b661ba94b76940`; this change records
the shared revision after checking its public files against the existing
SHA-256 values. No patch bytes change.

NixOS inherits fprintd's v1.94.5 source from nixpkgs revision
`e7439b6b14ad3cc35d05608ebca9bce01a25f5f8` in `flake.lock`; its fetcher fixes the
unpacked source hash to `sha256-aGIz50S0zfE3rV6QJp8iQz3uUVn8WAL68KU70j8GyOU=`.
Fedora and Arch use the v1.94.5 archive SHA-256
`a026ef34c31b25975275cc29a5e4eba2b54524769672095a5228098a08acd82c`.
Distro-specific service paths and policy packaging remain distro adaptations;
Arch and NixOS do not ship Fedora's SELinux modules.
