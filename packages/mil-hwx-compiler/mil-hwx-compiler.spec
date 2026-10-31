%global libane_commit 1adf2ee392ef7d3d64a24743d293dbc1670f0e8b
%global libs_base_commit 3d7013e144b153abcd6c088dc8d6c64ebd43bc4b
%global tools_make_commit d0349cc83a23367acdc53df364f73504c281b26c
%global libobjc2_commit a1faad66cee79f29c4ca268b004111edc33a2ae2
%global commit 3837b4cc2f432754970dbff0f61a3397fede7478
Name: mil-hwx-compiler
Version: 0.1.0
Release: 1%{?dist}
Summary: Open MIL compiler with linked H13 scheduling and a MobileNet runner
License: MIT AND LGPL-2.1-or-later AND GPL-3.0-or-later
URL: https://github.com/aurora-silicon/mil-hwx-compiler
ExclusiveArch: aarch64
Source0: mil-hwx-compiler-3837b4cc2f432754970dbff0f61a3397fede7478.tar.gz
Source1: libobjc2-%{libobjc2_commit}.tar.gz
Source2: tools-make-%{tools_make_commit}.tar.gz
Source3: libs-base-%{libs_base_commit}.tar.gz
Source4: libane-%{libane_commit}.tar.gz
Source5: build-mil-hwxc
Source6: install-mil-hwxc
Source7: mil-hwxc
BuildRequires: clang lld cmake ninja-build make pkgconf-pkg-config python3 patchelf
BuildRequires: libffi-devel libxml2-devel libicu-devel openssl-devel zlib-devel robin-map-devel libdrm-devel
Requires: bash python3 python3-numpy
# The ARC libraries are private to this compiler, not a system runtime ABI.
%global __requires_exclude ^lib(gnustep-base|objc).*\\.so.*$
%global __provides_exclude_from ^%{_libexecdir}/mil-hwx-compiler/.*$

%description
The open compiler pinned to the merged linked/linked-l2 implementation.
An isolated GNUstep ARC runtime and the tools/h13-mobilenet runner are included.
No models, oracle binaries, services or device permission changes are installed.

%prep
%setup -q -n mil-hwx-compiler-%{commit} -a 1 -a 2 -a 3 -a 4

%build
bash %{SOURCE5} "$PWD" "$PWD" "$PWD/runtime"
make -C omarchy-ane-1adf2ee392ef7d3d64a24743d293dbc1670f0e8b/libane %{?_smp_mflags} CFLAGS="%{optflags} -fPIC"
cc %{optflags} -Iomarchy-ane-1adf2ee392ef7d3d64a24743d293dbc1670f0e8b/libane tools/h13-mobilenet/anechain.c omarchy-ane-1adf2ee392ef7d3d64a24743d293dbc1670f0e8b/libane/libane.a -ldrm -o tools/h13-mobilenet/anechain

%install
bash %{SOURCE6} "$PWD" "$PWD/runtime" "%{buildroot}" "%{_libexecdir}/mil-hwx-compiler/runtime"
install -Dm755 %{SOURCE7} %{buildroot}%{_bindir}/mil-hwxc
sed -i -e 's|@RUNTIME@|%{_libexecdir}/mil-hwx-compiler/runtime|g' -e 's|@COMPILER@|%{_libexecdir}/mil-hwx-compiler/mil-hwxc|g' %{buildroot}%{_bindir}/mil-hwxc
mkdir -p %{buildroot}%{_licensedir}/%{name}
cp LICENSE %{buildroot}%{_licensedir}/%{name}/compiler-MIT
cp libobjc2-a1faad66cee79f29c4ca268b004111edc33a2ae2/COPYING %{buildroot}%{_licensedir}/%{name}/libobjc2-MIT
cp libs-base-3d7013e144b153abcd6c088dc8d6c64ebd43bc4b/COPYING.LIB %{buildroot}%{_licensedir}/%{name}/GNUstep-LGPL
cp tools-make-d0349cc83a23367acdc53df364f73504c281b26c/COPYING %{buildroot}%{_licensedir}/%{name}/GNUstep-GPL
cp omarchy-ane-1adf2ee392ef7d3d64a24743d293dbc1670f0e8b/LICENSE %{buildroot}%{_licensedir}/%{name}/libane-MIT

%files
%{_bindir}/mil-hwxc
%{_libexecdir}/mil-hwx-compiler/
%{_datadir}/mil-hwx-compiler/
%license %{_licensedir}/%{name}/
%changelog
* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-1
- Pin merged compiler 3837b4c; keep the modern ARC runtime private.
