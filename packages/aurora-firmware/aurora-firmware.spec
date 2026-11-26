Name: aurora-firmware
Version: 44
Release: 6%{?dist}
Summary: Aurora device firmware and peripheral ordering
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch

Requires: aurora-vendor-firmware bash kmod coreutils grep cpio
BuildRequires: systemd-rpm-macros
%{?systemd_requires}

Source100: 90-aurora-peripherals.preset
Source101: admit-peripherals.sh
Source102: aurora-firmware-order.conf
Source104: aurora-peripheral-firmware.sh
Source105: aurora-peripherals.service
Source106: module-setup.sh
Source107: verify-vendor-firmware.sh

%description
Aurora device firmware and peripheral ordering.

%prep

%build

%install
install -Dm644 %{_sourcedir}/aurora-firmware-order.conf %{buildroot}%{_modprobedir}/aurora-firmware-order.conf
install -Dm755 %{_sourcedir}/aurora-peripheral-firmware.sh %{buildroot}/usr/libexec/aurora/peripheral-firmware
install -Dm755 %{_sourcedir}/module-setup.sh %{buildroot}/usr/lib/dracut/modules.d/98aurora-peripherals/module-setup.sh
install -Dm755 %{_sourcedir}/admit-peripherals.sh %{buildroot}/usr/lib/dracut/modules.d/98aurora-peripherals/admit-peripherals.sh
install -Dm755 %{_sourcedir}/verify-vendor-firmware.sh %{buildroot}/usr/lib/dracut/modules.d/98aurora-peripherals/verify-vendor-firmware.sh
install -Dm644 %{_sourcedir}/aurora-peripherals.service %{buildroot}%{_unitdir}/aurora-peripherals.service
install -Dm644 %{_sourcedir}/90-aurora-peripherals.preset %{buildroot}/usr/lib/systemd/system-preset/90-aurora-peripherals.preset

%post
%systemd_post aurora-peripherals.service
%preun
%systemd_preun aurora-peripherals.service
%postun
%systemd_postun_with_restart aurora-peripherals.service

%files
%{_modprobedir}/aurora-firmware-order.conf
/usr/libexec/aurora/
/usr/lib/dracut/modules.d/98aurora-peripherals/
%{_unitdir}/aurora-peripherals.service
/usr/lib/systemd/system-preset/90-aurora-peripherals.preset

%changelog
* Thu Nov 26 2026 DjDeveloperr <hey@djdev.me> - 44-6
- On a signed boot, unpack only the vendor firmware archive whose digest
  the UKI command line names (aurora.vendorfw=); refuse any other.

* Tue Nov 24 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-5
- Require the Aurora vendor firmware loader.

* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 44-4
- Load the dockchannel keyboard and trackpad driver after firmware admission.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 44-3
- Apply systemd service presets and lifecycle hooks for peripheral firmware admission.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
