Name: aurora-firmware
Version: 44
Release: 1%{?dist}
Summary: Aurora device firmware and peripheral ordering
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch

Requires: dracut-asahi bash kmod coreutils grep
BuildRequires: systemd-rpm-macros

Source100: 90-aurora-peripherals.preset
Source101: admit-peripherals.sh
Source102: aurora-firmware-order.conf
Source104: aurora-peripheral-firmware.sh
Source105: aurora-peripherals.service
Source106: module-setup.sh

%description
Aurora device firmware and peripheral ordering.

%prep

%build

%install
install -Dm644 %{_sourcedir}/aurora-firmware-order.conf %{buildroot}%{_modprobedir}/aurora-firmware-order.conf
install -Dm755 %{_sourcedir}/aurora-peripheral-firmware.sh %{buildroot}/usr/libexec/aurora/peripheral-firmware
install -Dm755 %{_sourcedir}/module-setup.sh %{buildroot}/usr/lib/dracut/modules.d/98aurora-peripherals/module-setup.sh
install -Dm755 %{_sourcedir}/admit-peripherals.sh %{buildroot}/usr/lib/dracut/modules.d/98aurora-peripherals/admit-peripherals.sh
install -Dm644 %{_sourcedir}/aurora-peripherals.service %{buildroot}%{_unitdir}/aurora-peripherals.service
install -Dm644 %{_sourcedir}/90-aurora-peripherals.preset %{buildroot}/usr/lib/systemd/system-preset/90-aurora-peripherals.preset

%files
%{_modprobedir}/aurora-firmware-order.conf
/usr/libexec/aurora/
/usr/lib/dracut/modules.d/98aurora-peripherals/
%{_unitdir}/aurora-peripherals.service
/usr/lib/systemd/system-preset/90-aurora-peripherals.preset

%changelog
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
