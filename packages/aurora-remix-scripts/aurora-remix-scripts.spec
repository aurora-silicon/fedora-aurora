Name: aurora-remix-scripts
Version: 44
Release: 6%{?dist}
Summary: Fedora Aurora first-boot integration
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
Source0: aurora-firstboot
Source1: asahi-setup-swap-firstboot.service
Source2: asahi-extras-firstboot.service
Source4: complete-plasma-setup
Source5: aurora-display-manager-setup.conf
Requires: bash systemd util-linux coreutils python3 aurora-firstboot >= 0.1.8
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
install -Dm755 %{SOURCE4} %{buildroot}%{_libexecdir}/aurora/complete-plasma-setup
install -Dm644 %{SOURCE5} %{buildroot}%{_unitdir}/display-manager.service.d/aurora-plasma-setup.conf

%files
%{_libexecdir}/aurora/firstboot
%{_unitdir}/asahi-setup-swap-firstboot.service
%{_unitdir}/asahi-extras-firstboot.service
%{_libexecdir}/aurora/complete-plasma-setup
%{_unitdir}/display-manager.service.d/aurora-plasma-setup.conf

%changelog
* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 44-6
- Disable the two first-boot units without a daemon reload. Their reloads
  raced and aborted systemd 259, which froze the first boot at the splash.
* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 44-5
- Leave the Plasma Setup ordering to aurora-firstboot, which now lets Plasma
  Setup create the owner after the disk is protected.
* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 44-4
- Skip Plasma Setup while Aurora setup is pending instead of requiring it, so a
  failed or interrupted setup no longer cascades into dependency failures.
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 44-3
- Retire the generated Plasma Setup autologin before starting the greeter.
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 44-2
- Order Plasma Setup after Aurora owner creation and skip its duplicate wizard.
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 44-1
- Initial first-boot integration.
