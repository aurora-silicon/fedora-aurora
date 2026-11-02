Name: aurora-repos
Version: 44
Release: 3%{?dist}
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
Source105: aurora-override.repo

%description
The Aurora Silicon repository definition and its signing key, together with
the dnf5 vendor change policies that let Aurora's packages and Fedora's
replace each other on upgrade where allow_vendor_change is off, as on Fedora
Asahi Remix. Any system that uses the Aurora repository gets the policies with
it, whether it runs Aurora Fedora Remix or Fedora Asahi Remix with Aurora's
platform packages. This package has no vendor, so it installs and upgrades
before any vendor change is needed. A dnf5 repository override sets how the
repository is verified, even where the repository file was changed locally.

%prep

%build

%install
install -Dm644 %{SOURCE100} %{buildroot}%{_sysconfdir}/yum.repos.d/aurora.repo
install -Dm644 %{SOURCE101} %{buildroot}%{_sysconfdir}/pki/rpm-gpg/RPM-GPG-KEY-aurora
install -Dm644 %{SOURCE102} %{buildroot}/usr/share/dnf5/vendors.d/aurora.conf
install -Dm644 %{SOURCE103} %{buildroot}/usr/share/dnf5/vendors.d/aurora-asahi.conf
install -Dm644 %{SOURCE104} %{buildroot}/usr/share/dnf5/vendors.d/aurora-unvendored.conf
install -Dm644 %{SOURCE105} %{buildroot}/usr/share/dnf5/repos.override.d/50-aurora.repo

%files
%config(noreplace) %{_sysconfdir}/yum.repos.d/aurora.repo
%{_sysconfdir}/pki/rpm-gpg/RPM-GPG-KEY-aurora
/usr/share/dnf5/vendors.d/aurora*.conf
/usr/share/dnf5/repos.override.d/50-aurora.repo

%changelog
* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 44-3
- Follow the installed Fedora release: the repository URL uses $releasever
  instead of 44, and a release without an Aurora repository now fails the
  refresh instead of being skipped. An upgrade to such a release used to
  install it without Aurora's packages, or replace them with Fedora's.

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 44-2
- Check package signatures only. dnf5 asks before it trusts the repository
  metadata key, and a refresh that nobody answers, such as the makecache
  timer or any non-interactive dnf, skipped the repository and with it
  every Aurora update. A dnf5 repository override turns the metadata check
  off, so it also applies where aurora.repo was changed locally, as in an
  image built for another channel. dnf5 releases with
  auto_import_local_keys will import the package key without asking.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-1
- Own the Aurora repository file and signing key, which images used to write
  without a package, and carry the dnf5 vendor change policies that were in
  aurora-release 44-7, so systems that use the Aurora repository without
  aurora-release get them too.
