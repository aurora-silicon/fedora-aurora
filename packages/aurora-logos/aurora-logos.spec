Name: aurora-logos
Version: 44
Release: 4%{?dist}
Summary: Aurora Silicon desktop artwork
# Aurora artwork is MIT; the Breeze start-here artwork is LGPL-3.0-or-later.
License: MIT AND LGPL-3.0-or-later
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
# Breeze's start-here-kde, as breeze-icon-theme installs it.
Source200: breeze-start-here-kde-16.svg
Source201: breeze-start-here-kde-22.svg
Source202: breeze-start-here-kde-24.svg
Source203: breeze-start-here-kde-32.svg
Source204: breeze-start-here-kde-64.svg
Source205: breeze-start-here-kde-96.svg
Source206: breeze-COPYING-ICONS

%description
Aurora Silicon desktop artwork.

%prep
cp -p %{SOURCE206} .

%build

%install
# The Aurora logo is the distribution logo.
for size in 16 22 24 32 48 64 96 128 256 512; do
  install -Dm644 %{_sourcedir}/AuroraLogo-$size.png \
    %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/aurora-logo-icon.png
done
install -Dm644 %{_sourcedir}/AuroraLogo-256.png %{buildroot}%{_datadir}/pixmaps/system-logo-white.png
install -Dm644 %{_sourcedir}/AuroraLogo.png %{buildroot}%{_datadir}/backgrounds/aurora/logo.png
# Fedora's look-and-feel sets the Plasma launcher icon to start-here, which
# Breeze lacks; give it KDE's artwork, as stock Plasma shows.
for size in 16 22 24 32 64 96; do
  install -Dm644 %{_sourcedir}/breeze-start-here-kde-$size.svg \
    %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/places/start-here.svg
done
# Breeze fills the @2 directories too; KDE checks them first on scaled displays.
for size in 16 22 24; do
  install -Dm644 %{_sourcedir}/breeze-start-here-kde-$size.svg \
    %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}@2/places/start-here.svg
done

%files
%license breeze-COPYING-ICONS
%{_datadir}/icons/hicolor/*/apps/aurora-logo-icon.png
%{_datadir}/icons/hicolor/*/places/start-here.svg
%{_datadir}/pixmaps/system-logo-white.png
%{_datadir}/backgrounds/aurora/

%changelog
* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 44-4
- Shorten the spec comments; the installed files are unchanged.

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 44-3
- Show the KDE logo on the Plasma launcher, as stock Plasma does: start-here
  is now Breeze's start-here-kde artwork instead of the Aurora logo. The Aurora
  logo remains the distribution logo.

* Thu Oct 29 2026 Aurora Silicon <hey@djdev.me> - 44-2
- Provide start-here and system-logo-white.png, which fedora-logos supplied:
  the Plasma launcher and About this System showed blank icons.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
