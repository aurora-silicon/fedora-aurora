%global debug_package %{nil}
%global commit 0cb6fed6a10512d1013a4a80b6d83c3d56140f2f
Name: uboot-aurora
Version: 2026.07
Release: 1%{?dist}
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
%autosetup -n u-boot-0cb6fed6a10512d1013a4a80b6d83c3d56140f2f

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
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
