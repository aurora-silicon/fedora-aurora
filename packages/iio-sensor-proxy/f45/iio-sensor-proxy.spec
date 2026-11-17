Name:           iio-sensor-proxy
Version:        3.9
Release:        3%{?dist}.aurora1
Summary:        IIO accelerometer sensor to input device proxy

# tests/unittest_inspector.py is LGPL-2.1-or-later but it is not packaged
License:        GPL-3.0-or-later
URL:            https://gitlab.freedesktop.org/hadess/iio-sensor-proxy
Source0:        %{url}/-/archive/%{version}/%{name}-%{version}.tar.bz2

# Aurora: report the ambient light's colour temperature (ColorTemperature)
Patch0:         0001-light-report-ambient-colour-temperature.patch

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  git-core
BuildRequires:  gtk-doc
BuildRequires:  pkgconfig(udev)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gudev-1.0)
BuildRequires:  pkgconfig(polkit-gobject-1)
BuildRequires:  systemd
BuildRequires:  umockdev
BuildRequires:  python3-dbusmock
BuildRequires:  python3-gobject
BuildRequires:  python3-psutil
BuildRequires:  umockdev-devel
%{?systemd_requires}

%description
%{summary}.

%package docs
Summary:        Documentation for %{name}
License:        GFDL-1.1-or-later
BuildArch:      noarch

%description docs
This package contains the documentation for %{name}.

%prep
%autosetup -p1

%build
%meson -Dgtk_doc=true -Dgtk-tests=false -Dssc-support=disabled -Dtests=true
%meson_build

%install
%meson_install

%check
%meson_test

%post
%systemd_post %{name}.service

%preun
%systemd_preun %{name}.service

%postun
%systemd_postun_with_restart %{name}.service

%files
%license COPYING
%doc README.md
%{_bindir}/monitor-sensor
%{_libexecdir}/%{name}
%{_unitdir}/%{name}.service
%{_udevrulesdir}/*-%{name}.rules
%{_datadir}/dbus-1/system.d/net.hadess.SensorProxy.conf
%{_datadir}/polkit-1/actions/net.hadess.SensorProxy.policy

%files docs
%dir %{_datadir}/gtk-doc/
%dir %{_datadir}/gtk-doc/html/
%{_datadir}/gtk-doc/html/%{name}/

%changelog
* Wed Nov 11 2026 Ryan Murray <ryan@aurorasilicon.org> - 3.9-3.aurora1
- Fedora 45: follow Fedora's 3.9-3 with SSC support disabled (libssc is
  not packaged), keeping the ColorTemperature property and the tests;
  the release stays above Fedora's so the Aurora build replaces it
- Fedora 45 history is in Fedora dist-git rpms/iio-sensor-proxy (f45, fe0de0f)

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 3.8-2.aurora1
- Report the ambient light's correlated colour temperature as the
  ColorTemperature property, from the IIO in_colortemp_input channel
- Run the integration tests during the build
- Earlier history is in Fedora dist-git rpms/iio-sensor-proxy (f44, 4570bd3)

