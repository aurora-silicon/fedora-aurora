# Fedora Aurora Remix

Fedora-native packaging, image builds and the signed update repository for Aurora on Apple Silicon. The native macOS application lives in [aurora-installer](https://github.com/aurora-silicon/aurora-installer); [alarm-aurora](https://github.com/aurora-silicon/alarm-aurora) and [nixos-aurora](https://github.com/aurora-silicon/nixos-aurora) implement the other distribution choices.

## Build

All hardware sources are pinned by commit and SHA-256 in `sources.json`. RPM specs are under `packages/`; KIWI image configuration is under `images/`. Build a package on Fedora 44 AArch64:

```sh
sudo dnf install rpm-build dnf5-plugins python3 git
AURORA_INSTALL_BUILDDEPS=1 bash scripts/build-rpm aura
```

`out/rpms/` contains the binary RPMs and `out/srpms/` their reproducible source inputs. Kernel, bootloaders and graphics are built natively; matching kernel modules and DTBs come from the same build. `AURORA_BUILD_JOBS` bounds local parallelism.

## Updates and distribution

The initial update channel is `testing`. RPMs and repository metadata are signed with the public key in `keys/`; its full fingerprint is independently recorded in `keys/fingerprint.txt`. Private signing material is not stored in this repository. Versioned RPMs are served as immutable GitHub Release assets; static DNF metadata is served through GitHub Pages. Image and app release publication is separate from source CI and RPM candidate builds.

An image must consume an exact tested package set. Building RPMs, resolving an image, booting it and completing a physical installation are different validation stages. Until that sequence is complete, this repository is development infrastructure rather than an installable distribution release.

`aurora-firmware` 44-3 applies the peripheral service preset on first installation. Image builds reject a disabled peripheral admission service. Package updates preserve an administrator's disabled or masked service settings. Existing development images containing 44-2 need `sudo systemctl preset --now aurora-peripherals.service` after updating to adopt the default; this command is an explicit choice to apply that preset.

`aurora-remix-scripts` 44-2 orders Plasma Setup after Aurora account creation and skips its separate wizard once the Aurora Linux owner exists. It preserves the normal Plasma Login greeter and leaves Apple Recovery accounts untouched.

## Checks

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 images/test_configure.py
```

Actions run source tests and all RPM builds on native AArch64 Fedora. The image description retains Fedora's GRUB/BLS, dracut, SELinux and first-boot setup. Aurora supplies the hardware stack and its own release identity; firmware/calibration comes from the target Mac.

Software is covered by each upstream project's license. The image base is derived from the pinned Fedora Asahi KIWI description, whose GPL license is copied into each generated description. Aurora integration scripts are MIT-licensed. Branding assets retain their original attribution.
