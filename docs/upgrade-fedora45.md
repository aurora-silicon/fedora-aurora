# Upgrading from Fedora 44 to Fedora 45

Aurora Fedora Remix 44 upgrades to 45 with Fedora's own `dnf system-upgrade`.
No Aurora tool is needed: the Aurora repository follows the installed release,
and every Aurora package has a Fedora 45 build in `45/testing/aarch64`.

## Before you start

- The system must use the **testing** channel, which is the default. Fedora 45
  has no stable channel yet. On a system set to stable, the Aurora repository
  for 45 does not exist, and the upgrade stops before it changes anything
  (`skip_if_unavailable=False`).
- Bring Fedora 44 fully up to date and reboot if a kernel was updated:

  ```sh
  sudo dnf upgrade --refresh
  ```

- Keep a backup of anything you can't afford to lose. A finished upgrade can't
  be rolled back to Fedora 44.

## Upgrade

```sh
sudo dnf system-upgrade download --releasever=45
sudo dnf offline reboot
```

The Mac reboots, applies the upgrade from the boot splash and then reboots into
Fedora 45. GNOME Software cannot do this upgrade; use the commands above (KDE
Discover may offer it too).

## What changes

- `aurora-release` 45 replaces 44: `/etc/os-release` reports
  `Aurora Fedora Remix 45` and `%{fedora}` is 45.
- `aurora.repo` uses `$releasever`, so dnf now reads
  `https://aurorasilicon.org/fedora-aurora/45/testing/aarch64`. The signing key
  is the same.
- Every Aurora package moves to its `.fc45` build. Aurora's builds of Fedora
  packages (NetworkManager, Mutter, PipeWire, UPower and others) follow Fedora
  45's versions where Fedora 45 is newer.
- The Fedora 45 `kernel-aurora` is installed through Fedora's kernel-install
  and dracut, with a new GRUB entry. `update-m1n1` rebuilds Stage 2
  (`/boot/efi/m1n1/boot.bin`) from the new kernel's device trees, and the Aura
  and U-Boot packages move to their Fedora 45 builds. Stage 1 is not touched.
- The Fedora 44 kernel stays installed as a fallback in the GRUB menu, as for
  any kernel update.

If the Fedora 45 repository was last published before the Fedora 44 one, a few
packages can go back one build to the Fedora 45 build of the same version.
They move forward again with the next `dnf upgrade`.

## Checks after the upgrade

```sh
cat /etc/os-release              # VERSION_ID=45
rpm -qa | grep '\.fc44'          # nothing Aurora is left on .fc44
dnf repo info aurora             # baseurl .../45/testing/aarch64
sudo dnf check
systemctl --failed
```

## Validation

`scripts/test-system-upgrade` runs this upgrade in a disposable Fedora 44
AArch64 container. It installs `aurora-release`, `aurora-repos`,
`aurora-platform` and the Aurora Mesa drivers from the signed Aurora repository
(the published testing feed, or `AURORA_REPOSITORY_URL`), updates Fedora 44,
runs `dnf system-upgrade download --releasever=45` and then the stored offline
transaction, the same way `dnf5-offline-transaction.service` does after the
reboot. It then checks the release identity, that no `.fc44` package is left,
that no Aurora package was removed, that the repository points at 45, that
`dnf check` passes, that nothing is left to upgrade, and that the Fedora 45
kernel, its device trees and Stage 2 are in place. `AURORA_EXTRA_PACKAGES`
adds packages to the Fedora 44 system, such as a desktop group.
