Name: speakersafetyd-aurora-profiles
Version: 1
Release: 1%{?dist}
Summary: speakersafetyd profiles for Aurora-supported Macs
License: GPL-2.0-only
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch

Source0: j616.conf
Source1: 96-speakersafetyd-aurora.rules

Requires: speakersafetyd
BuildRequires: systemd-rpm-macros

%description
Speaker protection profiles for speakersafetyd on Macs whose profile
speakersafetyd does not ship yet, and the udev rule that starts the daemon
for their speaker cards. The J616s profile is speakersafetyd's J316 model
with the J616 V/I sense layout. Without the daemon the kernel keeps the
speaker volumes locked.

%prep

%build

%install
install -Dm644 %{SOURCE0} %{buildroot}%{_datadir}/speakersafetyd/apple/j616.conf
install -Dm644 %{SOURCE1} %{buildroot}%{_udevrulesdir}/96-speakersafetyd-aurora.rules

%files
%{_datadir}/speakersafetyd/apple/j616.conf
%{_udevrulesdir}/96-speakersafetyd-aurora.rules

%changelog
* Sat Oct 24 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-1
- The J616s (MacBook Pro 16-inch M4 Pro/Max) profile, derived from
  speakersafetyd's j316.conf with the J616 sense channel layout.
