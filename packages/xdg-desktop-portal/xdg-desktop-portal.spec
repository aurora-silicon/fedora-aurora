%global flatpak_version 1.5.0
%global geoclue_version 2.5.2
%global glib_version 2.76
%global low_memory_monitor_version 2.0
%global pipewire_version 0.2.90

Name:    xdg-desktop-portal
Version: 1.22.1
# Fedora's recipe (rpms/xdg-desktop-portal f44) with the credential portal;
# keeps Fedora's package name so desktop dependencies resolve normally.
Release: 1%{?dist}.aurora1
Summary: Portal frontend service to flatpak

# doc/website is CC0-1.0 but it is not included in rpm
License: LGPL-2.1-or-later
URL:     https://github.com/flatpak/xdg-desktop-portal/
Source0: xdg-desktop-portal-%{version}.tar.xz
# The experimental credential portal (org.freedesktop.portal.experimental.Credential)
# that hands WebAuthn requests to credentialsd: xdg-desktop-portal PR 2036
# (libdex D-Bus skeletons, which it needs) and PR 1889, rebased on 1.22.1
# as openSUSE carries them (home:MSirringhaus:webauthn_devel).
Patch1:  0001-xdp-pr-2036-dex-dbus-skeletons.patch
Patch2:  0002-xdp-pr-1889-credential-portal.patch
# Both were written against main, which builds with libdex and its
# gdbus-codegen extension; 1.22.1 needs that added.
Patch3:  0003-build-use-libdex-and-its-gdbus-codegen-extension.patch
# The capability properties (isUserVerifyingPlatformAuthenticatorAvailable)
# follow credentialsd's GetClientCapabilities(), and the portal finds
# credentialsd without a desktop portals.conf entry.
Patch4:  0004-credential-follow-the-handler-s-client-capabilities.patch

BuildRequires: gcc
BuildRequires: gettext
BuildRequires: meson
BuildRequires: systemd-rpm-macros
BuildRequires: pkgconfig(flatpak) >= %{flatpak_version}
BuildRequires: pkgconfig(fuse3)
BuildRequires: pkgconfig(gdk-pixbuf-2.0)
BuildRequires: pkgconfig(gio-unix-2.0) >= %{glib_version}
BuildRequires: pkgconfig(gstreamer-pbutils-1.0)
BuildRequires: pkgconfig(json-glib-1.0)
BuildRequires: pkgconfig(libdex-1) >= 1.1
# libdex's gdbus-codegen extension
BuildRequires: python3-libdex
BuildRequires: pkgconfig(libgeoclue-2.0) >= %{geoclue_version}
BuildRequires: pkgconfig(libpipewire-0.3) >= %{pipewire_version}
BuildRequires: pkgconfig(libsystemd)
BuildRequires: pkgconfig(umockdev-1.0)
BuildRequires: python3-dbusmock
BuildRequires: python3-gobject-base
BuildRequires: python3-pytest
BuildRequires: python3-pytest-xdist
BuildRequires: /usr/bin/gst-inspect-1.0
BuildRequires: gstreamer1-plugins-good
# for man-pages
BuildRequires: /usr/bin/rst2man

Requires:      dbus
Requires:      geoclue2 >= %{geoclue_version}
Requires:      glib2%{?_isa} >= %{glib_version}
Requires:      libdex%{?_isa} >= 1.1
Recommends:    pipewire >= %{pipewire_version}
Requires:      pipewire-libs%{?_isa} >= %{pipewire_version}
# Required for the document portal.
Requires:      fuse3
# The experimental credential portal, started with
# XDG_DESKTOP_PORTAL_ENABLE_EXPERIMENTAL=credential (credentialsd sets it).
Provides:      xdg-desktop-portal(credential) = 1

%description
xdg-desktop-portal works by exposing a series of D-Bus interfaces known as
portals under a well-known name (org.freedesktop.portal.Desktop) and object
path (/org/freedesktop/portal/desktop). The portal interfaces include APIs for
file access, opening URIs, printing and others.

This build adds the experimental credential portal for WebAuthn, served by
credentialsd.

%package  devel
Summary:  Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
The pkg-config file for %{name}.


%prep
%autosetup -p1


%build
%meson -Ddocumentation=disabled
%meson_build


%check
# The frontend's unit tests and the D-Bus API tests, the credential
# portal's interface included.
%meson_test


%install
%meson_install
install -dm 755 %{buildroot}/%{_pkgdocdir}
install -pm 644 README.md %{buildroot}/%{_pkgdocdir}
# This directory is used by implementations such as xdg-desktop-portal-gtk.
install -dm 755 %{buildroot}/%{_datadir}/xdg-desktop-portal/portals
test -f %{buildroot}%{_datadir}/dbus-1/interfaces/org.freedesktop.portal.experimental.Credential.xml
# The portal asks credentialsd for the capabilities (0004).
grep -q GetClientCapabilities %{buildroot}%{_libexecdir}/xdg-desktop-portal

%find_lang %{name}


%post
%systemd_user_post xdg-desktop-portal.service
%systemd_user_post xdg-document-portal.service
%systemd_user_post xdg-permission-store.service


%preun
%systemd_user_preun xdg-desktop-portal.service
%systemd_user_preun xdg-document-portal.service
%systemd_user_preun xdg-permission-store.service


%files -f %{name}.lang
%doc %{_pkgdocdir}
%license COPYING
%{_datadir}/dbus-1/interfaces/org.freedesktop.host.portal.Registry.xml
%{_datadir}/dbus-1/interfaces/org.freedesktop.portal.*.xml
%{_datadir}/dbus-1/interfaces/org.freedesktop.impl.portal.*.xml
%{_datadir}/dbus-1/services/org.freedesktop.portal.Desktop.service
%{_datadir}/dbus-1/services/org.freedesktop.portal.Documents.service
%{_datadir}/dbus-1/services/org.freedesktop.impl.portal.PermissionStore.service
%{_datadir}/xdg-desktop-portal/
%{_libexecdir}/xdg-desktop-portal
%{_libexecdir}/xdg-desktop-portal-rewrite-launchers
%{_libexecdir}/xdg-desktop-portal-validate-icon
%{_libexecdir}/xdg-desktop-portal-validate-sound
%{_libexecdir}/xdg-document-portal
%{_libexecdir}/xdg-permission-store
%{_mandir}/man5/portals.conf.5*
%{_userunitdir}/xdg-desktop-portal.service
%{_userunitdir}/xdg-desktop-portal-rewrite-launchers.service
%{_userunitdir}/xdg-document-portal.service
%{_userunitdir}/xdg-permission-store.service

%files devel
%{_datadir}/pkgconfig/xdg-desktop-portal.pc


%changelog
* Fri Nov 13 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 1.22.1-1.aurora1
- Fedora's 1.22.1-1 with the experimental credential portal (PR 2036 and
  PR 1889 as openSUSE carries them), capability properties from
  credentialsd's GetClientCapabilities(), and backend lookup for
  experimental interfaces without a portals.conf entry.
