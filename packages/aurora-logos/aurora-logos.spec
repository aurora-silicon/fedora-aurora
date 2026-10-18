Name: aurora-logos
Version: 44
Release: 1%{?dist}
Summary: Aurora Silicon desktop artwork
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
Provides: system-logos
Conflicts: fedora-logos fedora-logos-httpd

Source100: AuroraLogo.png

%description
Aurora Silicon desktop artwork.

%prep

%build

%install
install -Dm644 %{_sourcedir}/AuroraLogo.png %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/aurora-logo-icon.png
install -Dm644 %{_sourcedir}/AuroraLogo.png %{buildroot}%{_datadir}/backgrounds/aurora/logo.png

%files
%{_datadir}/icons/hicolor/512x512/apps/aurora-logo-icon.png
%{_datadir}/backgrounds/aurora/

%changelog
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
