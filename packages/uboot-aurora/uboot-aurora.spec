%global debug_package %{nil}
%global commit 2409ad5a25f88ec5ef42e1afdd6e29957a2fac96
Name: uboot-aurora
Version: 2026.07
Release: 4%{?dist}
Summary: Aurora U-Boot for Apple Silicon
License: GPL-2.0-or-later
URL: https://github.com/aurora-silicon/u-boot
Source0: uboot-aurora-%{commit}.tar.gz
ExclusiveArch: aarch64
Provides: uboot-images-armv8
Conflicts: uboot-images-armv8
BuildRequires: gcc make bc bison flex dtc python3 python3-pyelftools swig openssl-devel openssl-devel-engine gnutls-devel

%description
Aurora U-Boot for Apple Silicon. Built from the recorded Aurora source revision.

%prep
%autosetup -n u-boot-2409ad5a25f88ec5ef42e1afdd6e29957a2fac96

%build
make O=build-aurora apple_m1_defconfig
make O=build-aurora %{?_smp_mflags}

%install
install -Dm644 build-aurora/u-boot-nodtb.bin %{buildroot}%{_datadir}/uboot/apple_m1/u-boot-nodtb.bin
install -Dm644 build-aurora/u-boot-nodtb.bin %{buildroot}/usr/lib/asahi-boot/u-boot-nodtb.bin

%files
%license Licenses/gpl-2.0.txt
%{_datadir}/uboot/apple_m1/
/usr/lib/asahi-boot/u-boot-nodtb.bin

%changelog
* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 2026.07-4
- Track U-Boot aurora-wip at 2409ad5, the U-Boot that ships with
  aura 1.0.0b1.
- MacBook Pro M4 Pro (J616s, T6040) boot support, NVMe included.
- Boot from the ESP that holds the EFI boot loader, without a serial
  console or a countdown on the Aurora EFI path.
- Name the SPI keyboard spikbd in stdin, and start the MacBook Neo
  keyboard before autoboot.
- MacBook Air M4 (J713): carry the SEP boot manifests and AOP
  reservations into the OS tree.

* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 2026.07-3
- Track U-Boot aurora-wip at 7680260.
- MacBook Neo: answer the firmware of the adopted NVMe session, expose only
  the main namespace, and reset the controller when a command never
  completes, so that GRUB searching every disk no longer wedges the queue.
- Start the console with the 16x32 font on HiDPI panels, for U-Boot and
  GRUB's text menu.
- MacBook Air M4 (J713) boot support; other Macs keep booting if its
  handoff step fails.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
