Name: aurora-release
Version: 44
Release: 1%{?dist}
Summary: Fedora Aurora Remix release identity
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
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

%description
Fedora Aurora Remix release identity.

%prep

%build

%install
install -Dm644 %{_sourcedir}/os-release %{buildroot}/usr/lib/os-release
install -Dm644 %{_sourcedir}/system-release %{buildroot}/etc/fedora-release
ln -s fedora-release %{buildroot}/etc/redhat-release
ln -s fedora-release %{buildroot}/etc/system-release
install -Dm644 %{_sourcedir}/system-release-cpe %{buildroot}/etc/system-release-cpe


%files
/usr/lib/os-release
/etc/fedora-release
/etc/redhat-release
/etc/system-release
/etc/system-release-cpe

%changelog
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
