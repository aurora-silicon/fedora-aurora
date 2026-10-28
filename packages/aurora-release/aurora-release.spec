Name: aurora-release
Version: 44
Release: 3%{?dist}
Summary: Fedora Aurora Remix release identity
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
BuildRequires: fedora-release-common
BuildRequires: systemd-rpm-macros
Provides: system-release = 44
Provides: system-release(44)
Provides: fedora-release = 44
Provides: fedora-release-common = 44
Provides: fedora-release-identity-basic = 44
Provides: fedora-release-identity-workstation = 44
Provides: fedora-release-identity-kde = 44
Provides: fedora-release-workstation = 44
Provides: fedora-release-kde = 44
Conflicts: fedora-release-common fedora-release-identity-basic fedora-release-identity-workstation fedora-release-identity-kde
Requires: fedora-repos(44) fedora-gpg-keys

Source101: os-release
Source102: system-release
Source103: system-release-cpe
Source104: macros.dist
Source105: malcontent-signal.conf
Source106: malcontent-webd-update-signal.conf

%description
Fedora Aurora Remix release identity.

%prep

%build

%install
install -Dm644 %{_sourcedir}/os-release %{buildroot}/usr/lib/os-release
mkdir -p %{buildroot}/etc
ln -s ../usr/lib/os-release %{buildroot}/etc/os-release
install -Dm644 %{SOURCE104} %{buildroot}/usr/lib/rpm/macros.d/macros.dist
# Preserve Fedora's service and DNF policy defaults while replacing identity.
for path in /usr/lib/systemd/system-preset/{85-display-manager,90-default,99-default-disable}.preset /usr/lib/systemd/user-preset/{90-default-user,99-default-disable}.preset /usr/share/dnf5/libdnf.conf.d/20-fedora-defaults.conf; do
  install -Dm644 "$path" "%{buildroot}$path"
done
install -Dm644 /usr/share/licenses/fedora-release-common/LICENSE %{buildroot}%{_licensedir}/%{name}/fedora-release-LICENSE
install -Dm644 %{_sourcedir}/system-release %{buildroot}/etc/fedora-release
ln -s fedora-release %{buildroot}/etc/redhat-release
ln -s fedora-release %{buildroot}/etc/system-release
install -Dm644 %{_sourcedir}/system-release-cpe %{buildroot}/etc/system-release-cpe
for unit in malcontent-timerd malcontent-timer-extension-agent malcontent-webd; do
  install -Dm644 %{SOURCE105} %{buildroot}%{_unitdir}/$unit.service.d/50-aurora-signal.conf
done
install -Dm644 %{SOURCE106} %{buildroot}%{_unitdir}/malcontent-webd-update.service.d/50-aurora-signal.conf


%files
/usr/lib/os-release
/etc/os-release
/usr/lib/rpm/macros.d/macros.dist
/usr/lib/systemd/system-preset/*.preset
/usr/lib/systemd/user-preset/*.preset
/usr/share/dnf5/libdnf.conf.d/20-fedora-defaults.conf
%license %{_licensedir}/%{name}/fedora-release-LICENSE
/etc/fedora-release
/etc/redhat-release
/etc/system-release
/etc/system-release-cpe
%dir %{_unitdir}/malcontent-*.service.d
%{_unitdir}/malcontent-*.service.d/50-aurora-signal.conf

%changelog
* Thu Oct 29 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-3
- Let the malcontent daemons stop on SIGTERM (upstream af8226a7d3c3), so a
  reboot soon after login no longer waits 30 s for malcontent-timerd

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
