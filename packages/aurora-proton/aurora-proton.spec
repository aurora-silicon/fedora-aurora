# Preserve GE's private runtime, loaders, PE modules and component licences.
# Only the rebuilt native ntdll is replaced; RPM must not rewrite the bundle.
%global debug_package %{nil}
%global _build_id_links none
%global __os_install_post %{nil}
%global upstream_version 11-9
%global revision Aurora-Proton%{upstream_version}-%{release}
%global proton_dir %{_datadir}/aurora-proton/%{revision}
Name: aurora-proton
Version: 11.9
Release: 1%{?dist}
Summary: Native ARM64 GE-Proton with Aurora's SME signal-frame fix
License: BSD-3-Clause AND LGPL-2.1-or-later AND OFL-1.1
URL: https://github.com/GloriousEggroll/proton-ge-custom
Source0: GE-Proton11-9-aarch64.tar.gz
Source1: 981e2f0b9007fd70a6e0ed6119cb18f4164e26f9.tar.gz
Source2: GE-Proton11-9.tar.gz
Source3: 6cc805ea57132eeaf44764e9213823c9b8d0d300.tar.gz
Source4: e813ca5771658b00875924ab88d525322e50d39f.patch
Source5: vk.xml
Source6: video.xml
Source7: build-ntdll.sh
Source8: verify-proton.py
Source9: prepare-proton
Source10: README.md
Patch0: wine-sve-guard.patch
ExclusiveArch: aarch64
AutoReqProv: no
BuildRequires: gcc gcc-c++ make clang lld llvm autoconf bison flex perl python3
BuildRequires: pkgconf-pkg-config patchelf util-linux patch gawk tar gzip binutils
Requires: bash coreutils python3 glibc

%description
GE-Proton11-9's native AArch64 release with a rebuilt Wine ntdll that safely
handles SME-only SVE signal records. The exact GE and Wine-Staging source
preparation is reproduced before applying Aurora's fix. The remaining GE
runtime keeps its original loaders, paths and bundled component licences.
Steam prepares a writable per-user copy so Aurora Play can manage its own
settings without modifying packaged files or replacing user settings.

%prep
%setup -q -n GE-Proton%{upstream_version}-aarch64

%build
bash %{SOURCE7} "$PWD/aurora-wine-build" %{SOURCE1} %{SOURCE2} %{SOURCE3} %{SOURCE4} %{SOURCE5} %{SOURCE6} %{PATCH0}
python3 %{SOURCE8} files/lib/wine/aarch64-unix/ntdll.so aurora-wine-build/ge/wine/build/dlls/ntdll/ntdll.so

%check
python3 %{SOURCE8} files/lib/wine/aarch64-unix/ntdll.so %{buildroot}%{proton_dir}/files/lib/wine/aarch64-unix/ntdll.so

%install
mkdir -p %{buildroot}%{proton_dir}
tar -xf %{SOURCE0} --strip-components=1 -C %{buildroot}%{proton_dir}
install -m755 aurora-wine-build/ge/wine/build/dlls/ntdll/ntdll.so %{buildroot}%{proton_dir}/files/lib/wine/aarch64-unix/ntdll.so
sed -i 's/GE-Proton%{upstream_version}-aarch64/Aurora-Proton%{upstream_version}/g' %{buildroot}%{proton_dir}/compatibilitytool.vdf
ln -s %{revision} %{buildroot}%{_datadir}/aurora-proton/current
sed 's|@PROTON@|%{_datadir}/aurora-proton/current|g' %{SOURCE9} > prepare-proton
install -Dm755 prepare-proton %{buildroot}%{_libexecdir}/aurora-proton/prepare-proton
install -Dm644 %{SOURCE10} %{buildroot}%{_docdir}/%{name}/README.md
install -Dm644 %{PATCH0} %{buildroot}%{_docdir}/%{name}/wine-sve-guard.patch

%files
%{_datadir}/aurora-proton/
%{_libexecdir}/aurora-proton/
%{_docdir}/%{name}/

%changelog
* Sat Nov 07 2026 Aurora Silicon <hey@djdev.me> - 11.9-1
- Package native GE-Proton11-9 with exact GE/Wine-Staging preparation and
  the Aurora SME signal-record fix; retain the bundled runtime layout.
