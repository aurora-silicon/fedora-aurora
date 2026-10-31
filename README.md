# Aurora Fedora Remix

Fedora-native packaging, image builds and the signed update repository for Aurora on Apple Silicon. The native macOS application lives in [aurora-installer](https://github.com/aurora-silicon/aurora-installer); [alarm-aurora](https://github.com/aurora-silicon/alarm-aurora) and [nixos-aurora](https://github.com/aurora-silicon/nixos-aurora) implement the other distribution choices.

## Build

All hardware sources are pinned by commit and SHA-256 in `sources.json`. RPM specs are under `packages/`; KIWI image configuration is under `images/`. Build a package on Fedora 44 AArch64:

```sh
sudo dnf install rpm-build dnf5-plugins python3 git
AURORA_INSTALL_BUILDDEPS=1 bash scripts/build-rpm aura
```

`out/rpms/` contains the binary RPMs and `out/srpms/` their reproducible source inputs. Kernel, bootloaders and graphics are built natively; matching kernel modules and DTBs come from the same build. `AURORA_BUILD_JOBS` bounds local parallelism.

The platform includes `avd-fw` from Aurora's firmware fork and `upower` from Aurora's battery-reporting fork. The latter retains Fedora's `upower`, `upower-libs` and `upower-devel` package names so desktop dependencies resolve normally. Its native build runs the macsmc battery-time regression tests. Firmware builds retain the linked symbols for all six decoder variants.

`aurora-flatpak-gl` gives Flatpak apps the same Mesa as the rest of the system. Flatpak apps load OpenGL and Vulkan from the runtime's GL extension, so without it they run Flathub's `GL.default`. `build-extension.sh` in the package directory builds `org.freedesktop.Platform.GL.aurora` for a runtime branch from the `mesa-aurora` commit into a local OSTree repository. The RPM always carries that repository, installs the extension into the system installation and sets `FLATPAK_GL_DRIVERS=aurora:default:host`. `scripts/build-rpm aurora-flatpak-gl` builds both supported branches, or accepts a prepared archive through `AURORA_FLATPAK_GL_REPO_TAR`. The build needs flatpak-builder, both Freedesktop SDKs and an unprivileged user with bubblewrap sandbox support; CI supplies that environment. The extension has a higher priority than `GL.default` and ships the same file names, so its Asahi ICD, EGL vendor file and DRI drivers replace Flathub's in the merged GL directories. Runtime branches without a `GL.aurora` build keep `GL.default`. The recipe follows the `mesa-aurora` commit, Version and Release like `mesa-aurora-fex-guest`. Both the export and RPM build validate the committed libraries, architecture, loader JSONs and embedded Mesa identity for each supported branch. A settings-only or partial repository cannot produce a successful RPM. Removing the package removes the extension, the remote and its override keys.

## Updates and distribution

See [the release procedure](RELEASING.md) for package publication, image and catalog pairing, native installer delivery, hardware qualification and snapshot restoration.

[docs/updates.md](docs/updates.md) covers source tracking, automatic publication, the testing and stable channels and the signing environments.

The initial update channel is `testing`. RPMs and repository metadata are signed with the public key in `keys/`; its full fingerprint is independently recorded in `keys/fingerprint.txt`. Private signing material is not stored in this repository. Versioned RPMs are served as immutable GitHub Release assets; static DNF metadata is served through GitHub Pages. Image and app release publication is separate from source CI and RPM candidate builds. Publication accepts successful native CI runs whose commits are merged into `main`, with identical package recipes, source pins, build tooling and verified output receipts. Incremental publication takes an immutable `base-release`, authenticates its RPMs with the committed Aurora key, replaces every output of rebuilt source packages, and requires coverage at the current recipes' source versions before signing. A partial first snapshot or stale base kernel is rejected.

Each new testing release retains `repository-metadata-<tag>.tar.gz` and its detached Aurora signature alongside the RPM assets. The archive preserves the signed metadata index, each checksum-verified referenced metadata file, package manifest and public key. `deploy-snapshot.yml` authenticates this archive and its signed index before restoring an update snapshot. The archive excludes RPM copies and has bounded, normalized paths and deterministic bytes.

An image must consume an exact tested package set. Building RPMs, resolving an image, booting it and completing a physical installation are different validation stages. Until that sequence is complete, this repository is development infrastructure rather than an installable distribution release.

`aurora-firmware` 44-3 applies the peripheral service preset on first installation. Image builds reject a disabled peripheral admission service. Package updates preserve an administrator's disabled or masked service settings. Existing development images containing 44-2 need `sudo systemctl preset --now aurora-peripherals.service` after updating to adopt the default; this command is an explicit choice to apply that preset.

`aurora-firstboot` 0.1.8 creates the owner with the desktop's own setup on KDE and GNOME images: the first boot asks for the disk password on the boot splash, replaces the temporary encryption key with it and destroys both copies of that key, then Plasma Setup or GNOME Initial Setup creates the account before the greeter. The minimal image keeps a full-screen text wizard, and `aurora.firstboot=text` on the kernel command line starts it for recovery while no owner exists. The package ships an SELinux policy module that labels Aurora's first-boot programs as ordinary executables, so systemd runs them in `unconfined_service_t` with SELinux enforcing; earlier images ran them in `init_t`, where `chpasswd` is denied. It also keeps GRUB's lookups on the startup disk and reapplies that after GRUB updates. Images boot with `quiet loglevel=3 rd.udev.log_level=3 systemd.show_status=auto`, and image composition rejects a desktop image without its account setup.

`aurora-remix-scripts` 44-5 retires Plasma Setup's generated automatic login once Aurora's text wizard has created the owner.

Image builds run `scripts/check-basics.py` on the finished filesystems after `finalize-image`. The root is mounted read-only from `root.img`; the EFI files and `boot.img` are read as the installer writes them. The build fails unless the image has a generated UTF-8 default locale, its desktop's terminal (Ptyxis, Console or gnome-terminal; Konsole) with a launcher, GNOME's backgrounds with an existing default picture or Plasma's wallpapers, NetworkManager enabled with the desktop's network settings, logind's lid-close suspend left in place, and a GRUB stub that finds /boot by its UUID marker on the startup disk with hinted lookups only.

## Checks

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 images/test_configure.py
```

Actions run source tests and all RPM builds on native AArch64 Fedora. The image description retains Fedora's GRUB/BLS, dracut, SELinux and first-boot setup. Aurora supplies the hardware stack and its own release identity; firmware/calibration comes from the target Mac.

Software is covered by each upstream project's license. The image base is derived from the pinned Fedora Asahi KIWI description, whose GPL license is copied into each generated description. Aurora integration scripts are MIT-licensed. Branding assets retain their original attribution.

The shared kernel enables the integrated microphone/camera/audio/haptics stack
and common USB4/Thunderbolt PCIe networking, storage, USB audio and external GPU
modules. Firmware for Intel Wi-Fi and AMD/Intel/NVIDIA GPUs is a hard platform
dependency so minimal images do not silently omit it with weak dependencies
disabled. Physical dock, storage and external GPU qualification remains pending.

SEP initialization is supplied by `aurora-sep` and the Aurora `libfprint` build.
The boot timer defers probing until persistent state is available, extracts local
calibration where present and verifies trusted-key sealing and unsealing. No
calibration is redistributed. The full reader driver set remains enabled; the
native libfprint build runs all 130 upstream/patched tests. Password policy and
power-button behavior are unchanged. Real SEP hardware qualification is pending.

Bluetooth LE Audio defaults, opt-out instructions and the three-distro parity
table are documented in [Bluetooth LE Audio](docs/bluetooth-le-audio.md).
