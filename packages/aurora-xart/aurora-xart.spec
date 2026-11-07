%global commit aab11591fec7723b58db9386da031f67cd74f13c
Name: aurora-xart
Version: 0.1.0
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
* Sat Nov 07 2026 Diljit Singh <hey@djdev.me> - 0.1.0-1
- Package aurora-xart aab11591fec7: status, list and reset-touchid for the
  Linux side of the Secure Enclave and xART state.
