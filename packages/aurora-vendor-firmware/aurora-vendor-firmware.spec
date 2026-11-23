%global commit 800400dcf9612edd10f00d306a39a499313cefe3
%global dracutdir %{_prefix}/lib/dracut

Name: aurora-vendor-firmware
Version: 20250713
Release: 2%{?dist}
Summary: Load the target Mac's firmware from its EFI system partition
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
Source0: aurora-vendor-firmware-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: systemd-rpm-macros
Requires: dracut cpio systemd-udev
# Replace Fedora's matching dracut hook and directory-owner package together.
# Existing firmware consumers still know the old dracut module names.
Provides: dracut-asahi = %{version}-%{release}
# Retained boot helpers still require the old package name and source path.
Provides: asahi-scripts = %{version}-%{release}
Obsoletes: asahi-scripts < 20250714
Obsoletes: dracut-asahi < 20250714
Obsoletes: linux-firmware-vendor < 20250714

%description
Load the firmware supplied by the installer for this Mac into the initramfs
and hand it off to the running system. The RPM contains loader scripts only.

%prep
%setup -q -n asahi-scripts-%{commit}
# Keep the dracut module names and hook priorities until all consumers move.
sed -i 's|/usr/share/asahi-scripts|/usr/share/aurora-vendor-firmware|g' \
    dracut/modules.d/99asahi-firmware/*.sh

%build

%install
install -Dm644 functions.sh %{buildroot}%{_datadir}/aurora-vendor-firmware/functions.sh
install -d %{buildroot}%{_datadir}/asahi-scripts
ln -s ../aurora-vendor-firmware/functions.sh %{buildroot}%{_datadir}/asahi-scripts/functions.sh
install -Dm644 dracut/dracut.conf.d/10-asahi.conf %{buildroot}%{dracutdir}/dracut.conf.d/10-aurora-vendor-firmware.conf
for module in 91kernel-modules-asahi 99asahi-firmware; do
    install -d %{buildroot}%{dracutdir}/modules.d/$module
    install -m755 dracut/modules.d/$module/*.sh %{buildroot}%{dracutdir}/modules.d/$module/
done
install -Dm644 udev/hwdb.d/65-autosuspend-override-asahi-sdhci.hwdb \
    %{buildroot}%{_udevhwdbdir}/65-autosuspend-override-aurora-sdhci.hwdb
install -d %{buildroot}%{_prefix}/lib/firmware/vendor

%files
%license LICENSE
%{_datadir}/aurora-vendor-firmware/
%{_datadir}/asahi-scripts/
%{dracutdir}/dracut.conf.d/10-aurora-vendor-firmware.conf
%{dracutdir}/modules.d/91kernel-modules-asahi/
%{dracutdir}/modules.d/99asahi-firmware/
%{_udevhwdbdir}/65-autosuspend-override-aurora-sdhci.hwdb
%dir %{_prefix}/lib/firmware/vendor

%changelog
* Tue Nov 24 2026 Ryan Murray <ryan@aurorasilicon.org> - 20250713-2
- Replace the old helper RPM and keep its source path for pinned updaters.

* Mon Nov 23 2026 Ryan Murray <ryan@aurorasilicon.org> - 20250713-1
- Package the firmware handoff separately from redistributable firmware.
