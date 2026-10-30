Name: aurora-logos
Version: 44
Release: 2%{?dist}
Summary: Aurora Silicon desktop artwork
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
Provides: system-logos
Conflicts: fedora-logos fedora-logos-httpd

Source100: AuroraLogo.png
Source101: AuroraLogo-16.png
Source102: AuroraLogo-22.png
Source103: AuroraLogo-24.png
Source104: AuroraLogo-32.png
Source105: AuroraLogo-48.png
Source106: AuroraLogo-64.png
Source107: AuroraLogo-96.png
Source108: AuroraLogo-128.png
Source109: AuroraLogo-256.png
Source110: AuroraLogo-512.png

%description
Aurora Silicon desktop artwork.

%prep

%build

%install
# fedora-logos supplied these names. Fedora's Plasma look-and-feel sets the
# launcher icon to start-here, which Breeze lacks, and kcm-about-distrorc
# shows system-logo-white.png; without them both render as blank icons.
for size in 16 22 24 32 48 64 96 128 256 512; do
  install -Dm644 %{_sourcedir}/AuroraLogo-$size.png \
    %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/aurora-logo-icon.png
  install -Dm644 %{_sourcedir}/AuroraLogo-$size.png \
    %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/places/start-here.png
done
install -Dm644 %{_sourcedir}/AuroraLogo-256.png %{buildroot}%{_datadir}/pixmaps/system-logo-white.png
install -Dm644 %{_sourcedir}/AuroraLogo.png %{buildroot}%{_datadir}/backgrounds/aurora/logo.png

%files
%{_datadir}/icons/hicolor/*/apps/aurora-logo-icon.png
%{_datadir}/icons/hicolor/*/places/start-here.png
%{_datadir}/pixmaps/system-logo-white.png
%{_datadir}/backgrounds/aurora/

%changelog
* Thu Oct 29 2026 Aurora Silicon <hey@djdev.me> - 44-2
- Provide start-here and system-logo-white.png, which fedora-logos supplied:
  the Plasma launcher and About this System showed blank icons.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
