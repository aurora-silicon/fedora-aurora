Name: aurora-remix-scripts
Version: 44
Release: 8%{?dist}
Summary: Aurora Fedora Remix first-boot integration
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
Source4: complete-plasma-setup
Source5: aurora-display-manager-setup.conf
Requires: bash systemd util-linux coreutils python3 aurora-firstboot >= 0.1.8
BuildRequires: systemd-rpm-macros
Provides: fedora-asahi-remix-scripts
Conflicts: fedora-asahi-remix-scripts

%description
Plasma Setup integration for Aurora Fedora Remix.

%prep
%build
%install
install -Dm755 %{SOURCE4} %{buildroot}%{_libexecdir}/aurora/complete-plasma-setup
install -Dm644 %{SOURCE5} %{buildroot}%{_unitdir}/display-manager.service.d/aurora-plasma-setup.conf

%files
%{_libexecdir}/aurora/complete-plasma-setup
%{_unitdir}/display-manager.service.d/aurora-plasma-setup.conf

%changelog
* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 44-8
- Drop the first-boot swap and extras units. They only disabled
  themselves, and the presets systemd applies on the first boot turn
  them off.
* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 44-7
- Name the distribution Aurora Fedora Remix in the package text and in the
  first-boot unit descriptions.
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
