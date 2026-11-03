# Graphics packaging parity for the fleet

Mesa source is `c208afc352e9d4c10ee71c883a369a9079dd7d84` (26.3.0-14, accepts the "aurora" kernel DRM name; earlier sections below describe cf4e08105dfa).
Fedora packaging release 26.3.0-11 fixes delivery and migration; it does not
change driver source. These are text-only proposals for the other distributions.

## alarm-aurora

Reviewed public main `80de98bdcf362ecd7fffcd4a14f4ded1b457ae92`.

- `packages/mesa-aurora/PKGBUILD`: export
  `MESA_GIT_SHA1_OVERRIDE=$_commit` before both Meson configurations and in
  `check()` (Meson may regenerate its always-stale Git header), and check
  `libvulkan_asahi.so` for `(git-cf4e08105d), Borealis`. This recipe uses a Git
  source, so it can currently discover the commit, but the explicit override
  also covers archived sources and prevents an unrelated checkout's identity.
- `packages/aurora-flatpak-gl/build-extension.sh` and `validate-repo.sh`: use
  explicit runtime export with `--runtime --files=files`, stamp the payload,
  and validate OSTree checkouts for both 25.08 and 26.08. Require AArch64 GL,
  EGL, Vulkan and DRI libraries, JSON targets and embedded commit. The existing
  PKGBUILD already builds both branches and copies the repository; the Fedora
  settings-only CI failure is not present there. Its existing stamp/subject
  checks alone do not prove libraries exist. Update PKGBUILD source checksums.
- `packages/mesa-aurora/PKGBUILD`: add a Rusticl OpenCL split package if OpenCL
  is to remain available when replacing stock Mesa; build Rusticl in the
  LLVM-enabled tool tree and keep compiler runtime dependencies confined to
  that package. Audit pacman `provides/conflicts/replaces` against the actual
  installed OpenCL package names. Arch has no Fedora `mesa-libgbm = EVR`
  subpackage dependency to copy verbatim. Keep headers and GBM interfaces
  provided by `mesa-aurora`; check a real pacman upgrade before delivery.
  Bump all three graphics recipes' pkgrel together.

## nixos-aurora

Reviewed public main `5a7df1963bc131cdd69710de4f122574113b657f`.

- `mesa.nix` already sets `env.MESA_GIT_SHA1_OVERRIDE = commit`; retain it and
  assert the installed Vulkan library contains the expected driverInfo.
- `flatpak-gl/package.nix` already builds both branches, stamps payloads and
  validates the combined repository. Make export's `--runtime --files=files`
  explicit; extend `flatpak-gl/validate-repository.py` to check ELF architecture,
  GL/EGL/DRI libraries, loader JSON targets and the embedded commit, not only
  ref/stamp metadata. Retain SDK locks and the isolated build environment.
- `mesa.nix`/`overlay.nix`: add a separate Rusticl derivation/output from the
  same pin if native OpenCL parity is required, enabling LLVM and SPIRV-Tools
  only for Rusticl. The existing native/guest GL drivers deliberately forbid
  those runtime references. Nix closures have no DNF exact-version migration;
  preserve the matching Mesa `dev`/OpenCL interfaces and test a generation
  switch and rollback instead of adding RPM Obsoletes.

## Scope and validation boundaries

Fedora's new `mesa-aurora-devel`, `mesa-aurora-libOpenCL` and
`mesa-aurora-libOpenCL-devel` provide and obsolete the corresponding old
subpackage names. Their exact dependencies point at the *new matching*
Aurora runtime packages, so a single DNF transaction replaces the whole
version-coupled set. OpenCL provides a real Rusticl library and ICD; it does
not advertise a capability from an empty migration package. The development
package owns the headers, pkg-config files and GBM linker interface formerly
swept into DRI. GL/Vulkan remain free of LLVM/SPIRV-Tools runtime dependencies.

The original Flatpak failure was the default `%bcond repo 0` combined with
`scripts/build-rpm`/CI never supplying `--with repo` or Source10. The successful
settings-only RPM contained no OSTree objects. A separate extension build can
finish successfully without its result being used by the RPM job. Source10 is
now unconditional, the normal builder constructs or consumes it, and the spec
checks the committed payload. Native `%check` also exports the commit because Meson
regenerates its always-stale Git header when tests rebuild. Explicit `--files=files` follows Flatpak's
extension build layout rather than relying on export defaults; see the
[upstream command reference](https://flatpak-docs.readthedocs.io/en/latest/flatpak-command-reference.html).

Out of scope: Fedora 45 rebuilds; mutter/GNOME 51 compatibility and builds;
J616s upower Fedora 45 rebase; publication/signing; fleet installation and GPU
runtime qualification. Fedora 45 kits remain blocked on matching builds and
exact rollback inventory. A Fedora 44 container solve does not qualify a
Fedora 45 desktop or prove GPU behavior on any machine.

## Fedora 44 artifact proof

- [Flatpak and FEX build](https://github.com/aurora-silicon/fedora-aurora/actions/runs/41086858578):
  both 25.08/26.08 committed payloads validated during export and RPM construction;
  x86_64/i686 guest ELF identities match the same source pin.
- [Native build](https://github.com/aurora-silicon/fedora-aurora/actions/runs/41094374085):
  121 Mesa tests passed; the installed Vulkan library contains
  `Mesa 26.3.0-devel (git-cf4e08105d), Borealis, derived from Honeykrisp`.
- [Upgrade and rollback proof](https://github.com/aurora-silicon/fedora-aurora/actions/runs/41098056195):
  independent native AArch64 Fedora 44 containers upgraded the signed -9 and
  testing-20261030.11 graphics sets and Fedora's OpenCL/devel layout without
  force-erasing or skip flags. All three restored their original Mesa/Flatpak
  NEVRAs and payload identities in a single rollback transaction. Source checks
  passed 201 tests (one skip), 11 image tests and all graphics script syntax checks.

These are unsigned CI candidates for review. The test repository's unsigned
candidate policy is confined to disposable containers; owner-run kits retain
configured DNF trust and versionlock policy. No target or GPU runtime result is
claimed. Other userspace candidates remain separate references in the staged kits.

## Lavapipe (Fedora 26.3.0-12)

Fedora's old `mesa-vulkan-drivers` carried lavapipe (`libvulkan_lvp.so`), and
installed applications link it directly (the ChatGPT desktop app on the fleet
does). 26.3.0-12 builds it in the LLVM-enabled tools tree next to Rusticl and
ships it as `mesa-aurora-vulkan-lavapipe`, so the native Vulkan package keeps
no compiler runtime dependency. Fedora 45 builds against `pkgconfig(libclc)`,
which `libclc22-devel` provides there, and Rusticl requires `libclc22`.

- alarm-aurora (reviewed main `266655ede65b6b24e2376b3c097a0bf8de5831f7`):
  `mesa-aurora` builds only `-Dvulkan-drivers=asahi`, so lavapipe comes from
  Arch's stock `vulkan-swrast` (26.2.6), which still installs beside it.
  For one Mesa source, add a `vulkan-swrast-aurora` split package built in the
  LLVM-enabled tools tree with `provides=('vulkan-swrast')`,
  `conflicts=('vulkan-swrast')` and `replaces=('vulkan-swrast')`.
- nixos-aurora (reviewed main `afa9b4c734f426000b0a017d60dc9a6394258b8b`):
  `mesa.nix` sets `-Dvulkan-drivers=asahi`, so the system has no lavapipe at
  all, unlike stock nixpkgs Mesa. Build `src/gallium/targets/lavapipe` in the
  `tools` tree (which already has `-Dllvm=enabled`) and install
  `libvulkan_lvp.so` with its ICD into a separate output, keeping LLVM out of
  the native driver closure.
