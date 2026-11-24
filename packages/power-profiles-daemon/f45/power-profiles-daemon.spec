Name:           power-profiles-daemon
Version:        0.30
Release:        4%{?dist}.aurora1
Summary:        Makes power profiles handling available over D-Bus

License:        GPL-3.0-or-later
URL:            https://gitlab.freedesktop.org/upower/power-profiles-daemon
Source0:        %{url}/-/archive/%{version}/%{name}-%{version}.tar.bz2

# Aurora: use /sys/class/platform-profile on device tree boots without ACPI
Patch0:         0001-platform-profile-use-the-class-interface-without-acpi.patch

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  gtk-doc
BuildRequires:  argparse-manpage
BuildRequires:  pkgconfig(bash-completion)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gudev-1.0)
BuildRequires:  pkgconfig(polkit-gobject-1)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  pkgconfig(upower-glib)
BuildRequires:  python3dist(shtab)
BuildRequires:  systemd-rpm-macros

# Test dependencies
BuildRequires:  umockdev
BuildRequires:  python3dist(python-dbusmock)
BuildRequires:  python3dist(pygobject)

# This is an implementation of the power-profiles-daemon service
Provides:       ppd-service
Conflicts:      ppd-service

%description
%{summary}.

%package docs
Summary:        Documentation for %{name}
BuildArch:      noarch

%description docs
This package contains the documentation for %{name}.

%prep
%autosetup -p1

%build
%meson \
    -Dgtk_doc=true \
    -Dpylint=disabled \
    -Dzshcomp=%{zsh_completions_dir}
%meson_build

%install
%meson_install
mkdir -p %{buildroot}/%{_localstatedir}/lib/power-profiles-daemon

%check
# Tests may fail when executed in parallel
%define _smp_build_ncpus 1
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
%{_bindir}/powerprofilesctl
%{_libexecdir}/%{name}
%{_unitdir}/%{name}.service
%{_datadir}/dbus-1/system.d/net.hadess.PowerProfiles.conf
%{_datadir}/dbus-1/system.d/org.freedesktop.UPower.PowerProfiles.conf
%{_datadir}/dbus-1/system-services/net.hadess.PowerProfiles.service
%{_datadir}/dbus-1/system-services/org.freedesktop.UPower.PowerProfiles.service
%{_datadir}/polkit-1/actions/power-profiles-daemon.policy
%dir %{_localstatedir}/lib/power-profiles-daemon/
%{_mandir}/man1/powerprofilesctl.1.gz
%{bash_completions_dir}/powerprofilesctl
%{zsh_completions_dir}/_powerprofilesctl

%files docs
%dir %{_datadir}/gtk-doc/
%dir %{_datadir}/gtk-doc/html/
%{_datadir}/gtk-doc/html/%{name}/

%changelog
* Wed Nov 25 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.30-4.aurora1
- Fall back to /sys/class/platform-profile when /sys/firmware/acpi/platform_profile
  is absent (device tree boots on Apple silicon, such as apple-clpc).
- Fedora 45 history is in Fedora dist-git rpms/power-profiles-daemon (f45).
