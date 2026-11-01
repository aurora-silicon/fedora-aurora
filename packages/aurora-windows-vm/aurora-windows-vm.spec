Name: aurora-windows-vm
Version: 0.1.0
Release: 1%{?dist}
Summary: Fail-closed Windows ARM64 VM launcher for UTM Neptune graphics
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
Source0: aurora-windows-vm
Source1: build-neptune-stack.sh
Source2: README.md
Source3: verify-guest-driver.ps1
Source4: patches/0001-neptune-directx-native-abi.patch
Source5: fetch-guest-driver.sh
BuildArch: noarch
Requires: bash

%description
Launches a Windows ARM64 virtual machine with UTM's Linux Neptune virtio-gpu
backend. The accelerated path requires a UTM QEMU/virglrenderer build and a
Vulkan D3D12 host backend. The launcher refuses plain 2D virtio-gpu unless
--no-gpu is explicitly requested.

%prep

%build

%install
install -Dm755 %{SOURCE0} %{buildroot}%{_bindir}/aurora-windows-vm
install -Dm755 %{SOURCE1} %{buildroot}%{_libexecdir}/aurora-windows-vm/build-neptune-stack.sh
install -Dm644 %{SOURCE2} %{buildroot}%{_pkgdocdir}/README.md
install -Dm644 %{SOURCE3} %{buildroot}%{_pkgdocdir}/verify-guest-driver.ps1
install -Dm644 %{SOURCE4} %{buildroot}%{_libexecdir}/aurora-windows-vm/patches/0001-neptune-directx-native-abi.patch
install -Dm755 %{SOURCE5} %{buildroot}%{_libexecdir}/aurora-windows-vm/fetch-guest-driver.sh

%files
%{_bindir}/aurora-windows-vm
%{_libexecdir}/aurora-windows-vm/build-neptune-stack.sh
%{_pkgdocdir}/README.md
%{_pkgdocdir}/verify-guest-driver.ps1
%{_libexecdir}/aurora-windows-vm/patches/0001-neptune-directx-native-abi.patch
%{_libexecdir}/aurora-windows-vm/fetch-guest-driver.sh

%changelog
* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-1
- Add a fail-closed UTM Neptune/Vulkan launcher and pinned host-stack builder.
