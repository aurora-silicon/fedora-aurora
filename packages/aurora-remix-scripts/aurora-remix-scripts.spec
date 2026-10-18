Name: aurora-remix-scripts
Version: 44
Release: 3%{?dist}
Summary: Fedora Aurora first-boot integration
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
Source0: aurora-firstboot
Source1: asahi-setup-swap-firstboot.service
Source2: asahi-extras-firstboot.service
Source3: aurora-plasma-setup.conf
Source4: complete-plasma-setup
Source5: aurora-display-manager-setup.conf
Requires: bash systemd util-linux coreutils python3 aurora-firstboot >= 0.1.2
BuildRequires: systemd-rpm-macros
Provides: fedora-asahi-remix-scripts
Conflicts: fedora-asahi-remix-scripts

%description
Initial swap and target-device integration for Fedora Aurora Remix.

%prep
%build
%install
install -Dm755 %{SOURCE0} %{buildroot}%{_libexecdir}/aurora/firstboot
install -Dm644 %{SOURCE1} %{buildroot}%{_unitdir}/asahi-setup-swap-firstboot.service
install -Dm644 %{SOURCE2} %{buildroot}%{_unitdir}/asahi-extras-firstboot.service
install -Dm644 %{SOURCE3} %{buildroot}%{_unitdir}/plasma-setup.service.d/aurora-firstboot.conf
install -Dm755 %{SOURCE4} %{buildroot}%{_libexecdir}/aurora/complete-plasma-setup
install -Dm644 %{SOURCE5} %{buildroot}%{_unitdir}/display-manager.service.d/aurora-plasma-setup.conf

%files
%{_libexecdir}/aurora/firstboot
%{_unitdir}/asahi-setup-swap-firstboot.service
%{_unitdir}/asahi-extras-firstboot.service
%{_unitdir}/plasma-setup.service.d/aurora-firstboot.conf
%{_libexecdir}/aurora/complete-plasma-setup
%{_unitdir}/display-manager.service.d/aurora-plasma-setup.conf

%changelog
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 44-3
- Retire the generated Plasma Setup autologin before starting the greeter.
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 44-2
- Order Plasma Setup after Aurora owner creation and skip its duplicate wizard.
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 44-1
- Initial first-boot integration.
