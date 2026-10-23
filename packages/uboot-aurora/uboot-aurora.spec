%global debug_package %{nil}
%global commit 38b39feacc5e636766b2cc69963c0b4b9242ad19
Name: uboot-aurora
Version: 2026.07
Release: 3%{?dist}
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
%autosetup -n u-boot-38b39feacc5e636766b2cc69963c0b4b9242ad19

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
* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 2026.07-3
- Track U-Boot aurora-wip at 38b39fe.
- MacBook Neo: answer the firmware of the adopted NVMe session, expose only
  the main namespace, and reset the controller when a command never
  completes, so that GRUB searching every disk no longer wedges the queue.
- Start the console with the 16x32 font on HiDPI panels, for U-Boot and
  GRUB's text menu.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
