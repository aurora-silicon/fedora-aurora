# Graphics packaging parity for the fleet

Mesa source remains `cf4e08105dfa526b8874318b6a52b3ce948f6297`.
Fedora packaging release 26.3.0-11 fixes delivery and migration; it does not
change driver source. These are text-only proposals for the other distributions.

## alarm-aurora

Reviewed public main `80de98bdcf362ecd7fffcd4a14f4ded1b457ae92`.

- `packages/mesa-aurora/PKGBUILD`: export
  `MESA_GIT_SHA1_OVERRIDE=$_commit` before both Meson configurations and check
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
