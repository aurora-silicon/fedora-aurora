Name: speakersafetyd-aurora-profiles
Version: 1
Release: 1%{?dist}
Summary: speakersafetyd profiles for Aurora-supported Macs
License: GPL-2.0-only
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch

Source0: j616.conf
Source1: 96-speakersafetyd-aurora.rules
Source2: 50-aurora-warm-restart.conf

Requires: speakersafetyd
BuildRequires: systemd-rpm-macros

%description
Speaker protection profiles for speakersafetyd on Macs whose profile
speakersafetyd does not ship yet, and the udev rule that starts the daemon
for their speaker cards. The J616s profile is speakersafetyd's J316 model
with the J616 V/I sense layout. Without the daemon the kernel keeps the
speaker volumes locked. A service drop-in gives the daemon its restart
flag back after any stop, so a restart within the same boot starts from
the worst-case temperature, as speakersafetyd intends.

%prep

%build

%install
install -Dm644 %{SOURCE0} %{buildroot}%{_datadir}/speakersafetyd/apple/j616.conf
install -Dm644 %{SOURCE1} %{buildroot}%{_udevrulesdir}/96-speakersafetyd-aurora.rules
install -Dm644 %{SOURCE2} %{buildroot}%{_unitdir}/speakersafetyd.service.d/50-aurora-warm-restart.conf

%files
%{_datadir}/speakersafetyd/apple/j616.conf
%{_udevrulesdir}/96-speakersafetyd-aurora.rules
%{_unitdir}/speakersafetyd.service.d/50-aurora-warm-restart.conf

%changelog
* Sat Oct 24 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-1
- The J616s (MacBook Pro 16-inch M4 Pro/Max) profile, derived from
  speakersafetyd's j316.conf with the J616 sense channel layout.
- Give speakersafetyd its restart flag back after any stop, so a restart
  within the same boot starts warm instead of cold.
