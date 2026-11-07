# Aurora Proton for ARM64

This package is GE-Proton11-9's native AArch64 release with one rebuilt Wine
`ntdll.so`. The internal Steam compatibility-tool name is `Aurora-Proton11-9`. RPM
version 11.9 corresponds to upstream release 11-9; the installed revision
includes the Fedora release (for example `Aurora-Proton11-9-1.fc44`).

`../../sources.json` pins the release archive, GE source, exact Wine commit, matching
Wine-Staging snapshot, configure restoration patch and Vulkan XML inputs.
`build-ntdll.sh` reproduces GE's own Wine patch preparation before applying
`wine-sve-guard.patch`. The patch checks the SVE signal-record extent before
writing FEX predicates, including SME-only/header-only records. Packaging
compares the complete exported-symbol sets, rejects added runtime libraries
or a newer GLIBC requirement, then restores the original library runtime path
before replacing it. The remaining release files keep their original
loaders, RPATHs and bundled runtime layout for Steam's container.

The recipes were adapted through `aurora-silicon/nixos-aurora` from
`mchalunderscore`'s `flake` repository, `pkgs/ge-proton-arm64/{default.nix,ntdll.nix}`.
The signal fix retains its author attribution and LGPL-2.1-or-later license.
GE's included component licenses remain in the packaged release; the packaging
code follows this repository's MIT license.

Steam prepares a writable copy under
`${XDG_DATA_HOME:-$HOME/.local/share}/aurora-proton/<package-revision>` before
its first launch and discovers it through `STEAM_EXTRA_COMPAT_TOOLS_PATHS`.
Copies belonging to older package revisions and user settings are retained.
An explicitly configured compatibility-tool path takes precedence; setting
`AURORA_STEAM_PROTON=0` disables default per-user preparation (the RPM remains installed).

Aurora Play discovers the configured native Wine tools, including GE-Proton
names, and changes only the `user_settings.py` files it owns. Games launch
through `/usr/bin/steam`, which enters the required 4 KiB process tree.
Building the tool and matching its library ABI do not establish game or
hardware compatibility.
