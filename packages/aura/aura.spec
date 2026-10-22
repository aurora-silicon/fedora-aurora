%global debug_package %{nil}
%global commit 8f4ee8808f593802d825bb8fbc6b99b90f46c402
Name: aura
Version: 0.1.0
Release: 2%{?dist}
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
%autosetup -n aura-8f4ee8808f593802d825bb8fbc6b99b90f46c402

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
* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-2
- Track aura main at 8f4ee88.
- Keep booting when the power table names a parent it does not list.
- Hand the M3 MacBook Air internal display over to the kernel when requested.
- Run an M1-M3 Stage 2 from above the chainloaded image.
- Restore secondary CPU start on older CPUs with locked reset vectors.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
