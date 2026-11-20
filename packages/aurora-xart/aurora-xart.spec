%global commit c0c56af99d1440d5350a66668cf1597cbfce7235
Name: aurora-xart
Version: 0.2.0
Release: 1%{?dist}
Summary: Inspect and manage the Linux side of the Secure Enclave and xART state
License: MIT
URL: https://github.com/aurora-silicon/aurora-xart
Source0: https://github.com/aurora-silicon/aurora-xart/archive/%{commit}/%{name}-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: make python3
Requires: python3
# reset-touchid opens the sensor through fprintd-list.
Recommends: fprintd

%description
Reads the Apple SEP driver's diagnostics and its state in /var/lib (the
Touch ID identity keybag slot, the catacombs, the machine ref-key and the
xART guard's list of Linux's records), says in plain words what is wrong and
what to do, and starts Touch ID over when its keybag is stuck
(aurora-xart reset-touchid). It never talks to the enclave, never writes
xART and never deletes a file.

%prep
%autosetup -n aurora-xart-%{commit}

%build

%check
make check

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%files
%license LICENSE
%doc %{_docdir}/aurora-xart
%{_bindir}/aurora-xart
%{_datadir}/aurora-xart
%{_mandir}/man8/aurora-xart.8*

%changelog
* Fri Nov 20 2026 Diljit Singh <hey@djdev.me> - 0.2.0-1
- Update to aurora-xart 0.2.0 (c0c56af99d14, aurora-xart#2): SEP writes are
  always on. A stale xart_writes or provision_keybag setting in modprobe.d or
  on the kernel command line is reported as obsolete and ignored, and
  reset-touchid follows the driver's effective state; on an older kernel it
  still refuses when the driver will not provision a keybag.

* Sat Nov 07 2026 Diljit Singh <hey@djdev.me> - 0.1.0-1
- Package aurora-xart 0.1.0 (tag v0.1.0, 83ae1899d0a7): status, list and
  reset-touchid for the Linux side of the Secure Enclave and xART state.
