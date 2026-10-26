%global debug_package %{nil}
%global commit ec4a6ab8b4252079e78196515577d73ef0a86135
Name: aura
Version: 0.1.0
Release: 6%{?dist}
Summary: Aurora bootloader for Apple Silicon
License: MIT AND GPL-2.0-only
URL: https://github.com/aurora-silicon/aura
Source0: aura-%{commit}.tar.gz
ExclusiveArch: aarch64
BuildRequires: clang llvm lld rust rust-src cargo make python3
Provides: m1n1 = 1.6.1
Conflicts: m1n1
Requires: update-m1n1 uboot-aurora

%description
Aurora bootloader for Apple Silicon. Built from the recorded Aurora source revision.

%prep
%autosetup -n aura-ec4a6ab8b4252079e78196515577d73ef0a86135

%build
export RUSTC_BOOTSTRAP=1
make %{?_smp_mflags} BUILDSTD=1 RELEASE=1 CHAINLOADING=1 USE_CLANG=1 BUILTIN_LOGO=aurora
mkdir -p ../aurora-stage1
cp build/aura.bin ../aurora-stage1/aura-raw.bin
cp build/aura.macho ../aurora-stage1/aura.macho
make clean
make %{?_smp_mflags} BUILDSTD=1 RELEASE=1 CHAINLOADING=1 ESP_STAGE2=1 USE_CLANG=1 BUILTIN_LOGO=aurora

%install
install -Dm644 build/aura.bin %{buildroot}%{_libdir}/m1n1/m1n1.bin
install -Dm644 build/aura.bin %{buildroot}/usr/lib/asahi-boot/m1n1.bin
install -Dm644 ../aurora-stage1/aura-raw.bin %{buildroot}%{_datadir}/aura/stage1/aura-raw.bin
install -Dm644 ../aurora-stage1/aura.macho %{buildroot}%{_datadir}/aura/stage1/aura.macho

%files
%license LICENSE 3rdparty_licenses/*
%{_libdir}/m1n1/
/usr/lib/asahi-boot/m1n1.bin
%{_datadir}/aura/

%changelog
* Mon Oct 26 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-6
- Track aurora-silicon/aura main at ec4a6ab.
- Upstream head: Merge pull request #8 from AxxzyWasTaken/t6041-ans-reserve

* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-5
- Track aura main at 553b566.
- Keep the load header's relocation inside the relocation padding, so
  Stage 1 and Stage 2 no longer grow by a stray 64 KiB.

* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-4
- Track aura main at b9ad403.
- Include all of omacom m1n1 integration/aurora, integration/neo included.
- Chainload a combined MacBook Neo Stage 2 that reaches firmware RO.

* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-3
- Track aura main at 22bab60.
- Start the display on the 13-inch M1 MacBook Pro instead of timing out.
- Accept empty successful replies to display power, mode and surface requests.
- Keep display firmware memory mapped when the firmware does not stop.

* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-2
- Track aura main at 8f4ee88.
- Keep booting when the power table names a parent it does not list.
- Hand the M3 MacBook Air internal display over to the kernel when requested.
- Run an M1-M3 Stage 2 from above the chainloaded image.
- Restore secondary CPU start on older CPUs with locked reset vectors.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
