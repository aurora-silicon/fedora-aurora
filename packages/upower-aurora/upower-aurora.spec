%global commit d8a24ffc5b9a49f71a28517f7c8b92b16701597a
Name: upower
Epoch: 1
Version: 1.91.5
Release: 3%{?dist}.aurora
Summary: Power management service with Aurora macsmc battery estimates
License: GPL-2.0-or-later
URL: https://github.com/aurora-silicon/upower
Source0: upower-aurora-%{commit}.tar.gz
Source1: upower-charge-limit-migrate
Source2: upower-charge-limit-migrate.service
ExclusiveArch: aarch64
BuildRequires: gcc redhat-rpm-config meson ninja-build gettext libxslt docbook-style-xsl
BuildRequires: pkgconfig(glib-2.0) pkgconfig(gobject-2.0) pkgconfig(gio-unix-2.0)
BuildRequires: pkgconfig(gobject-introspection-1.0) pkgconfig(gudev-1.0)
BuildRequires: pkgconfig(libimobiledevice-1.0) pkgconfig(libplist-2.0)
BuildRequires: pkgconfig(polkit-gobject-1) pkgconfig(libudev) pkgconfig(systemd)
BuildRequires: systemd-rpm-macros dbus-daemon python3-dbusmock python3-gobject python3-packaging
BuildRequires: umockdev pkgconfig(umockdev-1.0)
Requires: %{name}-libs%{?_isa} = %{epoch}:%{version}-%{release}
%{?systemd_requires}
# UPower owns the battery charge limit. asahi-battery saved and restored it
# too, behind UPower's back; its saved limit moves to UPower once
# (upower-charge-limit-migrate).
Obsoletes: asahi-battery < 20270101
Conflicts: asahi-battery

%description
UPower from the pinned Aurora fork. It retains valid macsmc kernel battery
estimates when the instantaneous energy rate is zero, with the normal
rate-based fallback for other power supplies. It replaces asahi-battery: a
charge limit that asahi-battery saved is handed to UPower on the next boot.

%package libs
Summary: Client library for UPower

%description libs
UPower client library and GObject introspection data.

%package devel
Summary: Development files for UPower
Requires: %{name}-libs%{?_isa} = %{epoch}:%{version}-%{release}

%description devel
Headers, pkg-config metadata and introspection sources for UPower clients.

%prep
%autosetup -n upower-%{commit}

%build
%meson -Dgtk-doc=false -Dman=true -Dinstalled_tests=false \
  -Dintrospection=enabled -Didevice=enabled -Dpolkit=enabled \
  -Dhistorydir=%{_sharedstatedir}/upower \
  -Dsystemdsystemunitdir=%{_unitdir}
%meson_build

%check
meson test -C %{_vpath_builddir} --list > registered-tests.txt
grep -q test_macsmc_kernel_time_at_zero_rate registered-tests.txt
grep -q test_other_supply_ignores_kernel_time registered-tests.txt
grep -q test_macsmc_kernel_time_charge_units registered-tests.txt
%meson_test --print-errorlogs

%install
%meson_install
%find_lang upower
install -Dpm0755 %{SOURCE1} %{buildroot}%{_libexecdir}/aurora/upower-charge-limit-migrate
install -Dpm0644 %{SOURCE2} %{buildroot}%{_unitdir}/upower-charge-limit-migrate.service
install -d %{buildroot}%{_unitdir}/upower.service.wants
ln -s ../upower-charge-limit-migrate.service %{buildroot}%{_unitdir}/upower.service.wants/

%post
%systemd_post upower.service

%preun
%systemd_preun upower.service

%postun
%systemd_postun_with_restart upower.service

%files -f upower.lang
%license COPYING
%doc README.md
%config(noreplace) %{_sysconfdir}/UPower/UPower.conf
%dir %{_sysconfdir}/UPower
%{_sysconfdir}/UPower/UPower.conf.d/
%{_bindir}/upower
%{_libexecdir}/upowerd
%{_unitdir}/upower.service
%{_unitdir}/upower-charge-limit-migrate.service
%dir %{_unitdir}/upower.service.wants
%{_unitdir}/upower.service.wants/upower-charge-limit-migrate.service
%dir %{_libexecdir}/aurora
%{_libexecdir}/aurora/upower-charge-limit-migrate
%{_datadir}/dbus-1/system-services/org.freedesktop.UPower.service
%{_datadir}/dbus-1/system.d/org.freedesktop.UPower.conf
%{_datadir}/polkit-1/actions/org.freedesktop.upower.policy
%{_datadir}/polkit-1/rules.d/org.freedesktop.upower.rules
%{_datadir}/zsh/site-functions/_upower
%{_udevrulesdir}/*-upower-*.rules
%{_udevhwdbdir}/*-upower-*.hwdb
%{_mandir}/man1/upower.1*
%{_mandir}/man7/UPower.7*
%{_mandir}/man8/upowerd.8*
%dir %{_sharedstatedir}/upower

%files libs
%license COPYING
%{_libdir}/libupower-glib.so.*
%{_libdir}/girepository-1.0/UPowerGlib-1.0.typelib

%files devel
%{_includedir}/libupower-glib/
%{_libdir}/libupower-glib.so
%{_libdir}/pkgconfig/upower-glib.pc
%{_datadir}/gir-1.0/UPowerGlib-1.0.gir
%{_datadir}/dbus-1/interfaces/org.freedesktop.UPower*.xml

%changelog
* Fri Nov 20 2026 Aurora Silicon <ryan@aurorasilicon.org> - 1:1.91.5-3
- Replace asahi-battery, so UPower is the only writer of the battery charge
  limit; hand a limit asahi-battery saved to UPower once, before upowerd starts.

* Fri Nov 06 2026 Aurora Silicon <ryan@aurorasilicon.org> - 1:1.91.5-2
- Export the composite KbdBacklight only while a keyboard backlight exists
  (upstream bb7af5f), so GNOME stops dimming a missing one on the Neo.

* Sat Oct 31 2026 Aurora Silicon <ryan@aurorasilicon.org> - 1:1.91.5-1
- Rebase the macsmc estimate fix onto 1.91.5; outrank stock Fedora.

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 1.91.4-1
- Package the Aurora macsmc battery estimate fix and its integration tests.
