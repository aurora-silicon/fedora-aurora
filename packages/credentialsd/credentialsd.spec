%global commit 3659aa69c6bfd4dfa24fc69daeba7ed42d35441c
Name:		credentialsd
Version:	0.4.0
Release:	1%{?dist}.aurora1
Summary:	Credential manager service for WebAuthn passkeys and security keys
# credentialsd is LGPL-3.0-only; the crates it links are listed in Cargo.lock.
License:	LGPL-3.0-only
URL:		https://github.com/linux-credentials/credentialsd
Source0:	credentialsd-%{commit}.tar.gz
# credentialsd main after 0.4.0, which the platform provider series needs.
Patch0:		0001-backport-main-v0.4.0..ca77b3e.patch
# Platform passkey providers (transport "internal"): a local authenticator,
# such as the Secure Enclave passkey agent in aurora-fido, registers with a
# drop-in in /usr/share/credentialsd/providers and is offered next to USB,
# NFC and hybrid.
Patch1:		0002-ui-Add-password-and-locked-states-for-platform-provi.patch
Patch2:		0003-daemon-Discover-platform-passkey-providers.patch
Patch3:		0004-daemon-Route-requests-to-platform-passkey-providers.patch
Patch4:		0005-daemon-Report-client-capabilities-to-the-portal.patch
Patch5:		0006-doc-Document-the-platform-provider-API.patch
Source1:	50-credentialsd.conf
ExclusiveArch:	aarch64

BuildRequires:	meson >= 1.5.0
BuildRequires:	rust >= 1.85
BuildRequires:	cargo
BuildRequires:	gcc
BuildRequires:	clang-devel
BuildRequires:	blueprint-compiler >= 0.20.4
BuildRequires:	desktop-file-utils
BuildRequires:	gettext
BuildRequires:	appstream
BuildRequires:	libxml2
BuildRequires:	systemd-rpm-macros
BuildRequires:	pkgconfig(dbus-1)
BuildRequires:	pkgconfig(gio-2.0)
BuildRequires:	pkgconfig(glib-2.0)
BuildRequires:	pkgconfig(gtk4)
BuildRequires:	pkgconfig(libnfc)
BuildRequires:	pkgconfig(libpcsclite)
BuildRequires:	pkgconfig(openssl)
BuildRequires:	pkgconfig(udev)
BuildRequires:	pkgconfig(libudev)
# The integration test starts its own session bus.
BuildRequires:	dbus-daemon
# The credential portal frontend (org.freedesktop.portal.experimental.Credential)
# that hands browser requests to this service.
Requires:	xdg-desktop-portal(credential)
Requires:	dbus
Requires:	pcsc-lite-libs
# Origin checks use the system Public Suffix List.
Requires:	publicsuffix-list

%description
credentialsd is a credential manager for Linux. Browsers and other apps ask
it, through the credential portal of xdg-desktop-portal, to create and use
WebAuthn passkeys. It talks to USB and NFC security keys and to phones over
the hybrid (QR code) transport, and shows its own trusted dialog for the
choice of authenticator, PIN entry and touch prompts.

This build also offers platform passkey providers: local authenticators
that register with a drop-in file in /usr/share/credentialsd/providers.
On Aurora, aurora-fido's Secure Enclave passkey agent is one, so Touch ID
passkeys work in browsers that use the portal.

%prep
%autosetup -p1 -n credentialsd-%{commit}

%build
%meson -Dprofile=release -Dcargo_locked=true \
	-Dfeature_daemon=enabled -Dfeature_gui=enabled \
	-Dfeature_web_extension=disabled -Dfeature_demo_client=disabled
%meson_build

%check
# Unit tests of the three crates, the D-Bus integration test (own bus),
# and the gschema and appdata validation.
%meson_test --timeout-multiplier 0

%install
%meson_install
%find_lang credentialsd-ui
install -Dpm644 %{SOURCE1} %{buildroot}%{_userunitdir}/xdg-desktop-portal.service.d/50-credentialsd.conf
install -d %{buildroot}%{_datadir}/credentialsd/providers
install -d %{buildroot}%{_sysconfdir}/credentialsd/providers
# xdg-desktop-portal (Aurora's build) picks this backend for the experimental
# Credential interface when no portals.conf names one.
grep -qx 'Interfaces=org.freedesktop.impl.portal.experimental.Credential' \
	%{buildroot}%{_datadir}/xdg-desktop-portal/portals/credentialsd.portal
grep -qx 'ExecStart=%{_bindir}/credentialsd' \
	%{buildroot}%{_userunitdir}/xyz.iinuwa.credentialsd.Credentials.service
grep -qx 'SystemdService=xyz.iinuwa.credentialsd.Credentials.service' \
	%{buildroot}%{_datadir}/dbus-1/services/xyz.iinuwa.credentialsd.Credentials.service

%files -f credentialsd-ui.lang
%license LICENSE.md
%doc README.md CHANGELOG.md ARCHITECTURE.md doc/api.md
%{_bindir}/credentialsd
%{_bindir}/credentialsd-ui
%{_datadir}/credentialsd/
%{_datadir}/credentialsd-ui/
%dir %{_sysconfdir}/credentialsd
%dir %{_sysconfdir}/credentialsd/providers
%{_datadir}/dbus-1/services/xyz.iinuwa.credentialsd.Credentials.service
%{_datadir}/dbus-1/services/xyz.iinuwa.credentialsd.UiControl.service
%{_userunitdir}/xyz.iinuwa.credentialsd.Credentials.service
%{_userunitdir}/xyz.iinuwa.credentialsd.UiControl.service
%{_datadir}/xdg-desktop-portal/portals/credentialsd.portal
%dir %{_userunitdir}/xdg-desktop-portal.service.d
%{_userunitdir}/xdg-desktop-portal.service.d/50-credentialsd.conf
%{_datadir}/glib-2.0/schemas/xyz.iinuwa.credentialsd.CredentialsUi.gschema.xml
%{_datadir}/metainfo/xyz.iinuwa.credentialsd.CredentialsUi.metainfo.xml
%{_datadir}/icons/hicolor/*/apps/xyz.iinuwa.credentialsd.CredentialsUi*

%changelog
* Fri Nov 13 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.4.0-1.aurora1
- credentialsd 0.4.0 with main up to ca77b3e and the platform passkey
  provider series (drop-in discovery, internal transport, password and
  locked states, GetClientCapabilities for the portal).
