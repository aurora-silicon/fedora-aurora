%global commit 6062e8516c0a751bc8e50f5d604a17395923189f
%global debug_package %{nil}
# These are bare-metal ARM firmware and retained linked symbols, not host code.
%global __strip /usr/bin/true
Name: avd-fw
Version: 0.1
Release: 4%{?dist}.aurora
Summary: Open Apple Video Decoder firmware from Aurora
License: MIT
URL: https://github.com/aurora-silicon/avd-fw
Source0: avd-fw-%{commit}.tar.gz
Source1: check-firmware.py
ExclusiveArch: aarch64
BuildRequires: clang22 llvm22 lld22 meson ninja-build python3

%description
Open replacement firmware for Apple Video Decoder generations v2 through v5,
including the MacBook Neo transport, built from the pinned Aurora source.

%prep
%autosetup -n avd-fw-%{commit}

%build
# Keep the already-qualified firmware bytes on Fedora 45 as well.
export PATH=%{_libdir}/llvm22/bin:$PATH
clang --version | grep -F "clang version 22."
unset CFLAGS CXXFLAGS CPPFLAGS LDFLAGS
meson setup --cross-file llvm.ini --prefix=%{_prefix} --libdir=lib \
  build
meson compile -C build

%check
python3 %{SOURCE1} build

%install
export PATH=%{_libdir}/llvm22/bin:$PATH
DESTDIR=%{buildroot} meson install -C build
chmod 644 %{buildroot}%{_prefix}/lib/firmware/apple/*.bin
mkdir -p %{buildroot}%{_prefix}/lib/debug/firmware/apple
install -m644 build/avd-fw-*.elf %{buildroot}%{_prefix}/lib/debug/firmware/apple/

%files
%license LICENSE
%{_prefix}/lib/firmware/apple/avd-fw-*.bin
%{_prefix}/lib/debug/firmware/apple/avd-fw-*.elf

%changelog
* Mon Nov 02 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1-4
- Select Fedora 45's versioned LLVM 22 tools so all eight qualified firmware
  image hashes remain unchanged; retain the reset-vector and ELF checks.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 0.1-3
- Update to 6062e851 for per-image codec VP pools and multi-VP decoding.
- Ship all eight images including v3-t2; enforce the clang 22 image hashes.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 0.1-2
- Update to 66c3911b: queue ABI 2, SRAM ring and VP DONE events.
- Ship all seven images including v5-t2; verify reproducible image hashes.
- Use upstream Meson defaults without host optimization flags.

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 0.1-1
- Package the pinned Aurora firmware including both v5 variants.
