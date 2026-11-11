%global commit b214617b17ad0e421a2661c42c6e3b77932ac155
Name: aurora-fido
Version: 0.1.0
Release: 1%{?dist}
Summary: Touch ID as a FIDO2/U2F security key (opt in)
License: MIT
URL: https://github.com/aurora-silicon/aurora-sep-userspace
Source0: https://github.com/aurora-silicon/aurora-sep-userspace/archive/%{commit}/%{name}-%{commit}.tar.gz
ExclusiveArch: aarch64
BuildRequires: gcc make pkgconf-pkg-config json-c-devel
BuildRequires: python3-devel python3-cryptography
BuildRequires: systemd-rpm-macros
Requires: aurora-sep
Requires: fprintd
Requires: python3 python3-cryptography python3-gobject-base
Requires: systemd-udev
# The password dialog of the touchid-or-password policy.
Requires: polkit
# The "Touch ID to sign in to <site>" notification.
Recommends: libnotify
Recommends: glib2
# Clients: browsers need nothing; these are the command-line tools.
Suggests: fido2-tools pam-u2f

%description
aurora-fidod makes this Mac's Secure Enclave and Touch ID look like a USB
security key to Linux: WebAuthn and passkeys in Firefox and Chromium, SSH
ecdsa-sk keys, pam_u2f and systemd-cryptenroll --fido2-device. Every
operation that needs the user asks for a Touch ID match.

It is installed off. Turn it on with `sudo aurora-fido enable`, off with
`sudo aurora-fido disable`; `aurora-fido status` says which key store it
uses. Keys live in the Secure Enclave when the kernel has /dev/sep-key and
are sealed by it otherwise (root on this Mac can copy sealed keys); see
/usr/share/doc/aurora-fido/fido.md.

%prep
%autosetup -n aurora-sep-userspace-%{commit}

%build
%make_build -C fido CFLAGS="%{optflags}" LDFLAGS="%{build_ldflags}" \
	PYTHON=%{python3} LIBEXECDIR=%{_libexecdir}/aurora-fido

%check
# Unit tests: software stand-ins, no root, no hardware.
make -C fido check PYTHON=%{python3}

%install
%make_install -C fido PREFIX=%{_prefix} LIBEXECDIR=%{_libexecdir}/aurora-fido \
	UNITDIR=%{_unitdir} UDEVRULESDIR=%{_udevrulesdir} PRESETDIR=%{_presetdir} \
	DOCDIR=%{_docdir}/%{name}
%py_byte_compile %{python3} %{buildroot}%{_prefix}/lib/aurora-fido

%post
%systemd_post aurora-fido.service
%preun
%systemd_preun aurora-fido.service
%postun
%systemd_postun_with_restart aurora-fido.service

%files
%license LICENSES/MIT.txt
%doc %{_docdir}/%{name}/fido.md
%{_bindir}/aurora-fido
%dir %{_libexecdir}/aurora-fido
%{_libexecdir}/aurora-fido/aurora-fidod
%{_libexecdir}/aurora-fido/aurora-fido-seal
%{_prefix}/lib/aurora-fido/
%{_unitdir}/aurora-fido.service
%{_presetdir}/90-aurora-fido.preset
%{_udevrulesdir}/60-aurora-fido.rules
%{_datadir}/polkit-1/actions/org.aurora.fido.policy
%dir %{_sysconfdir}/aurora-fido
%config(noreplace) %{_sysconfdir}/aurora-fido/aurora-fido.conf

%changelog
* Sun Nov 08 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1.0-1
- Package aurora-sep-userspace's fido/: Touch ID as a FIDO2/U2F security key,
  installed off (preset disable); aurora-fido enable|disable|status;
  per-credential policy as macOS (Touch ID or password by default, Touch ID
  only opt in). Idea by Erik (@erikwb).
