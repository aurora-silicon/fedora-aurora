Name: aurora-remix-scripts
Version: 44
Release: 1%{?dist}
Summary: Fedora Aurora first-boot integration
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
Source0: aurora-firstboot
Source1: asahi-setup-swap-firstboot.service
Source2: asahi-extras-firstboot.service
Requires: bash systemd util-linux coreutils
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

%files
%{_libexecdir}/aurora/firstboot
%{_unitdir}/asahi-setup-swap-firstboot.service
%{_unitdir}/asahi-extras-firstboot.service

%changelog
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 44-1
- Initial first-boot integration.
