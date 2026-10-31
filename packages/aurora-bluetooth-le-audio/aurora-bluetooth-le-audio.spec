Name: aurora-bluetooth-le-audio
Version: 0.1.0
Release: 1%{?dist}
Summary: Optional Aurora Bluetooth LE Audio defaults
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
BuildRequires: systemd-rpm-macros
Source0: le-audio.conf
Source1: bluetooth.service.conf
Source2: README.md
Source3: LICENSE
Requires: bluez >= 5.75
Requires: pipewire-libs >= 1.2
Requires: wireplumber >= 0.5

%description
Enable BlueZ experimental LE Audio profiles and the ISO socket feature, with
PipeWire LC3 endpoints managed by WirePlumber. The defaults are editable and
this package can be removed independently of the Aurora platform packages.
Installing it does not restart Bluetooth or pair any devices.

%prep

%build

%install
install -Dm644 %{SOURCE0} %{buildroot}%{_sysconfdir}/bluetooth/le-audio.conf
install -Dm644 %{SOURCE1} %{buildroot}%{_unitdir}/bluetooth.service.d/50-aurora-le-audio.conf
install -Dm644 %{SOURCE2} %{buildroot}%{_docdir}/%{name}/README.md
install -Dm644 %{SOURCE3} %{buildroot}%{_licensedir}/%{name}/LICENSE

%files
%config(noreplace) %{_sysconfdir}/bluetooth/le-audio.conf
%{_unitdir}/bluetooth.service.d/50-aurora-le-audio.conf
%doc %{_docdir}/%{name}/README.md
%license %{_licensedir}/%{name}/LICENSE

%changelog
* Sat Oct 31 2026 Aurora Silicon <ryan@aurorasilicon.org> - 0.1.0-1
- Offer removable BlueZ ISO and WirePlumber BAP defaults.
