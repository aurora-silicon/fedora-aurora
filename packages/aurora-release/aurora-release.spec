Name: aurora-release
Version: 44
Release: 10%{?dist}
Summary: Aurora Fedora Remix release identity
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
# The Aurora repository, its key and the dnf vendor policies.
Requires: aurora-repos
Requires: aurora-system-fixes = %{version}-%{release}

Source101: os-release
Source102: system-release
Source103: system-release-cpe
Source104: macros.dist
Source105: malcontent-signal.conf
Source106: malcontent-webd-update-signal.conf
Source107: 80-aurora-sshd.preset
Source108: 80-aurora-image.preset
Source109: drkonqi-ordering.conf
Source110: nm-dispatcher-persist.conf
Source111: plasma-setup-xdg-autostart.conf

%description
Aurora Fedora Remix release identity.

%package -n aurora-system-fixes
Summary: Aurora drop-ins for system services awaiting upstream fixes
Requires: systemd

%description -n aurora-system-fixes
systemd unit drop-ins and tmpfiles entries that carry fixes for Fedora
system services until the upstream release ships them. Each file names the
upstream change or problem that retires it. It does not change the
distribution identity, so it can be installed on any Fedora release Aurora
supports.

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
# Without Fedora's desktop identities, 90-default.preset would enable sshd.
install -Dm644 %{SOURCE107} %{buildroot}/usr/lib/systemd/system-preset/80-aurora-sshd.preset
install -Dm644 %{SOURCE108} %{buildroot}/usr/lib/systemd/system-preset/80-aurora-image.preset
install -Dm644 /usr/share/licenses/fedora-release-common/LICENSE %{buildroot}%{_licensedir}/%{name}/fedora-release-LICENSE
install -Dm644 %{_sourcedir}/system-release %{buildroot}/etc/fedora-release
ln -s fedora-release %{buildroot}/etc/redhat-release
ln -s fedora-release %{buildroot}/etc/system-release
install -Dm644 %{_sourcedir}/system-release-cpe %{buildroot}/etc/system-release-cpe
for unit in malcontent-timerd malcontent-timer-extension-agent malcontent-webd; do
  install -Dm644 %{SOURCE105} %{buildroot}%{_unitdir}/$unit.service.d/50-aurora-signal.conf
done
install -Dm644 %{SOURCE106} %{buildroot}%{_unitdir}/malcontent-webd-update.service.d/50-aurora-signal.conf
for unit in drkonqi-coredump-cleanup.timer drkonqi-sentry-postman.path; do
  install -Dm644 %{SOURCE109} %{buildroot}%{_userunitdir}/$unit.d/50-aurora-ordering.conf
done
install -Dm644 %{SOURCE110} %{buildroot}%{_unitdir}/NetworkManager-dispatcher.service.d/50-aurora-persist.conf
install -Dm644 %{SOURCE111} %{buildroot}%{_tmpfilesdir}/plasma-setup-xdg-autostart.conf


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

%files -n aurora-system-fixes
%dir %{_unitdir}/malcontent-*.service.d
%{_unitdir}/malcontent-*.service.d/50-aurora-signal.conf
%dir %{_userunitdir}/drkonqi-*.d
%{_userunitdir}/drkonqi-*.d/50-aurora-ordering.conf
%dir %{_unitdir}/NetworkManager-dispatcher.service.d
%{_unitdir}/NetworkManager-dispatcher.service.d/50-aurora-persist.conf
%{_tmpfilesdir}/plasma-setup-xdg-autostart.conf

%changelog
* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 44-10
- Break drkonqi's ordering cycle that every Plasma session stop logged
  (KDE bug 528003).
- Keep nm-dispatcher running until NetworkManager has stopped, so its
  D-Bus activation no longer fails on every shutdown (NetworkManager
  issue 1643).
- Keep Plasma Setup's autostart entry non-executable, so systemd no
  longer warns about it on every boot until setup completes.

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 44-9
- Preset the default targets and the systemd-resolved sockets on, so that
  the presets systemd applies on the first boot keep what the image and
  its packages enable.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-8
- Move the dnf5 vendor change policies to aurora-repos, which also owns the
  Aurora repository file and signing key, and require it.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-7
- Ship dnf5 vendor change policies so that Aurora's packages (vendor
  Aurora Silicon) and Fedora's can replace each other on upgrade where
  allow_vendor_change is off, as on Fedora Asahi Remix, including the
  Asahi packages Aurora supersedes and Aurora's earlier builds that have
  no vendor. This package itself stays without a vendor so that it can
  upgrade, and bring the policies, before any vendor change is needed.

* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 44-6
- Rename the distribution to Aurora Fedora Remix, the standard Fedora Remix
  naming, in os-release NAME and PRETTY_NAME and in /etc/fedora-release.
  ID, VARIANT_ID and LOGO are unchanged.

* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 44-5
- Preset sshd.service and sshd.socket off. Fedora's desktop identities did
  that in 81-desktop.preset, which this package does not carry, so images
  started the SSH server by default. A preset applies only when
  openssh-server is first installed; existing installs keep their setting.

* Thu Oct 29 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-4
- Move the malcontent unit drop-ins to a new aurora-system-fixes subpackage,
  so machines that keep their own release package can get them too;
  aurora-release requires it

* Thu Oct 29 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-3
- Let the malcontent daemons stop on SIGTERM (upstream af8226a7d3c3), so a
  reboot soon after login no longer waits 30 s for malcontent-timerd

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
