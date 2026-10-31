# Fedora 45 graphics candidates

The native and FEX recipes pin Mesa `aurora-wip` at
`9fe179df8bf1cec359d9e452fc9dfa8680285698`, the merge of
[mesa#122](https://github.com/aurora-silicon/mesa/pull/122).
The codeload archive SHA256 is
`c174eed7713256efd3a4289f34f5c529ebefffc227989e721bcc335ff90dd2a0`.
The version in that source remains `26.3.0-devel`.

## Source parity

| Distribution | Native Mesa source pin | FEX x86_64 + i686 | Package identity |
| --- | --- | --- | --- |
| Fedora | `9fe179df8bf1cec359d9e452fc9dfa8680285698` | same pin and archive | `1:26.3.0-14.fc45.aurora` |
| ALARM | `9fe179df8bf1cec359d9e452fc9dfa8680285698` | same pin and archive | `1:26.3.0_devel.202610310601.9fe179df8bf-1` |
| NixOS | `9fe179df8bf1cec359d9e452fc9dfa8680285698` | same `sources.json` record through the overlay | `26.3.0`, fixed-output archive hash |

This table records source parity, not output parity: Fedora builds the six
native outputs plus FEX; ALARM splits Rusticl/lavapipe from the same native build;
the NixOS native recipe currently enables neither Rusticl nor lavapipe.

The accompanying ALARM and NixOS source-pin changes are review candidates.
Fedora's six native outputs are DRI, Honeykrisp Vulkan, lavapipe, devel,
Rusticl OpenCL, and OpenCL devel. The FEX layer is a separate noarch RPM
containing x86_64/i686 ELF drivers, built on x86_64. Native GL/Honeykrisp
and the guest layer keep their existing checks excluding LLVM/SPIRV-Tools
runtime dependencies. Rusticl and lavapipe retain their compiler runtimes.

Fedora 45's libclc pkg-config provider is selected with `pkgconfig(libclc)`
in both build recipes, rather than assuming the unversioned `libclc` package
contains a `.pc` file. The native Rusticl package retains the Fedora 45
`libclc22` runtime requirement.

## Version ordering and migration

Native outputs and FEX use epoch **1**, including all versioned stock-name
Provides, Obsoletes, and exact internal/FEX Requires. This makes the fork's
ordering explicit over epoch-zero stock Fedora and previous fc44 Aurora
builds; `fc45` alone is not the version policy. Every output shares the
same epoch, version and release. External host recipe overrides must set
`host_epoch`, `host_version`, `host_release`, and `commit` together.

The new `Graphics Fedora 45` workflow runs for matching pull requests, main
updates and manual dispatch. It builds in Fedora 45 containers on
native ARM64 (host) and x86_64 (guest) CI runners. It runs recipe checks and
retains RPMs, SRPMs, receipts and Meson logs, including logs on failure.
Artifact names start with `graphics-fedora45-`, so the existing Fedora 44
publisher cannot consume them as ordinary `rpm-*` inputs. Publication,
signing and machine installation require separate work.

Before the new workflow is merged onto the default branch, dispatch the
existing source-check workflow with `gh workflow run checks.yml --ref <branch>
-f graphics_fedora45=true`. It calls the same graphics workflow through
`workflow_call`, including both builds and all transaction cases.

## Container upgrade and exact rollback

`scripts/test-graphics-fedora45-upgrade OLD REPOSITORY EVIDENCE` requires a
Fedora 45 AArch64 container and an existing local createrepo repository with
exactly the seven candidate binary RPMs. `OLD` is `stock` or a directory of
signed fc44 Mesa RPMs. Import `keys/RPM-GPG-KEY-aurora` for the latter.

The workflow tests independent RPM databases for stock Fedora 45 and these
public fc44 Aurora release sets:

| Baseline | Public release |
| --- | --- |
| `26.3.0-9.fc44.aurora` | `testing-20261030.10` |
| `26.3.0-10.fc44.aurora` | `testing-20261030.11` |
| `26.3.0-13.fc44.aurora` | `testing-20261031.1` |

Release checksums and baseline RPM signatures are checked before use. The
test retains exact baseline RPM bytes, records installed NEVRAs, checks
candidate architecture/epoch/version ordering with Python RPM bindings,
then runs an ordinary DNF upgrade without erase/skip flags. It tests all
seven output packages, preserves a direct lavapipe consumer where the
baseline has lavapipe (stock and -13), and checks
native/guest Borealis source identity plus Rusticl's library and ICD.
Rollback restores renamed stock packages or the older Aurora set in one
transaction. It checks exact Mesa NEVRAs and payload digests and rejects
unrelated package removal. `dnf check` must pass at every stage.

Evidence includes `before.tsv`, `candidate.tsv`, `upgrade.tsv`, `after.tsv`, `rollback.tsv`,
`driverInfo.txt`, `rollback-payload-identities.txt`, the retained old RPMs
under `rollback-rpms/` with SHA256 inventory, and the transaction log.
Unsigned candidate trust is confined to a disposable file repository.
These checks establish package transaction behavior; they do not qualify
GPU execution or a mounted FEX overlay on a reference machine. Existing FEX
scriptlet regression tests continue to cover stop/remount failure handling.

Flatpak GL implementation, SDK builds and runtime validation belong to
t-3411. Only its existing lockstep pin/version metadata moves with Mesa,
as required by the repositories' tracker and source consistency tests.
