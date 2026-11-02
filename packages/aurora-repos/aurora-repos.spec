Name: aurora-repos
Version: 44
Release: 2%{?dist}
Summary: Aurora Silicon package repository, signing key and dnf vendor policies
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch

# The vendor policies moved here from aurora-release 44-7.
Conflicts: aurora-release < 44-8

Source100: aurora.repo
Source101: RPM-GPG-KEY-aurora
Source102: aurora-vendors.conf
Source103: aurora-vendors-asahi.conf
Source104: aurora-vendors-unvendored.conf

%description
The Aurora Silicon repository definition and its signing key, together with
the dnf5 vendor change policies that let Aurora's packages and Fedora's
replace each other on upgrade where allow_vendor_change is off, as on Fedora
Asahi Remix. Any system that uses the Aurora repository gets the policies with
it, whether it runs Aurora Fedora Remix or Fedora Asahi Remix with Aurora's
platform packages. This package has no vendor, so it installs and upgrades
before any vendor change is needed.

%prep

%build

%install
install -Dm644 %{SOURCE100} %{buildroot}%{_sysconfdir}/yum.repos.d/aurora.repo
install -Dm644 %{SOURCE101} %{buildroot}%{_sysconfdir}/pki/rpm-gpg/RPM-GPG-KEY-aurora
install -Dm644 %{SOURCE102} %{buildroot}/usr/share/dnf5/vendors.d/aurora.conf
install -Dm644 %{SOURCE103} %{buildroot}/usr/share/dnf5/vendors.d/aurora-asahi.conf
install -Dm644 %{SOURCE104} %{buildroot}/usr/share/dnf5/vendors.d/aurora-unvendored.conf

%files
%config(noreplace) %{_sysconfdir}/yum.repos.d/aurora.repo
%{_sysconfdir}/pki/rpm-gpg/RPM-GPG-KEY-aurora
/usr/share/dnf5/vendors.d/aurora*.conf

%changelog
* Mon Nov 02 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-2
- Select the testing repository by Fedora $releasever for Fedora 44 and 45.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-1
- Own the Aurora repository file and signing key, which images used to write
  without a package, and carry the dnf5 vendor change policies that were in
  aurora-release 44-7, so systems that use the Aurora repository without
  aurora-release get them too.
