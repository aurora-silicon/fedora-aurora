Name: aurora-logos
Version: 44
Release: 3%{?dist}
Summary: Aurora Silicon desktop artwork
# The Aurora artwork is MIT. start-here is Breeze's start-here-kde artwork
# (breeze-icons 6.31.0), which is LGPL-3.0-or-later.
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
# breeze-icons 6.31.0 icons/places/<size>/start-here-kde.svg, symlinks
# resolved. The 24px file is the one breeze-icons' build generates from 22px,
# as breeze-icon-theme installs it.
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
# fedora-logos supplied these names: kcm-about-distrorc shows
# system-logo-white.png, and Fedora's Plasma look-and-feel (kde-settings-plasma)
# changes the launcher icon from Plasma's start-here-kde to start-here, which
# Breeze lacks. Without them both render as blank icons.
#
# start-here carries Breeze's own start-here-kde artwork at Breeze's sizes, so
# the Plasma launcher shows the KDE logo exactly as stock Plasma does. The
# Aurora logo stays the distribution logo: os-release LOGO=aurora-logo-icon and
# About this System.
for size in 16 22 24 32 48 64 96 128 256 512; do
  install -Dm644 %{_sourcedir}/AuroraLogo-$size.png \
    %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/aurora-logo-icon.png
done
for size in 16 22 24 32 64 96; do
  install -Dm644 %{_sourcedir}/breeze-start-here-kde-$size.svg \
    %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/places/start-here.svg
done
# Breeze has the same artwork in its 16@2x, 22@2x and 24@2x directories; KDE
# looks there first for scaled displays.
for size in 16 22 24; do
  install -Dm644 %{_sourcedir}/breeze-start-here-kde-$size.svg \
    %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}@2/places/start-here.svg
done
install -Dm644 %{_sourcedir}/AuroraLogo-256.png %{buildroot}%{_datadir}/pixmaps/system-logo-white.png
install -Dm644 %{_sourcedir}/AuroraLogo.png %{buildroot}%{_datadir}/backgrounds/aurora/logo.png

%files
%license breeze-COPYING-ICONS
%{_datadir}/icons/hicolor/*/apps/aurora-logo-icon.png
%{_datadir}/icons/hicolor/*/places/start-here.svg
%{_datadir}/pixmaps/system-logo-white.png
%{_datadir}/backgrounds/aurora/

%changelog
* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 44-3
- Show the KDE logo on the Plasma launcher, as stock Plasma does: start-here
  is now Breeze's start-here-kde artwork instead of the Aurora logo. The Aurora
  logo remains the distribution logo.

* Thu Oct 29 2026 Aurora Silicon <hey@djdev.me> - 44-2
- Provide start-here and system-logo-white.png, which fedora-logos supplied:
  the Plasma launcher and About this System showed blank icons.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
