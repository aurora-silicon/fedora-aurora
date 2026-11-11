%global commit 929b7b828401eb805aab9596615335d90534c01c
Name: aurora-fido
Version: 0.2.0
Release: 1%{?dist}
Summary: Touch ID as a FIDO2/U2F security key (opt in)
License: MIT
URL: https://github.com/aurora-silicon/aurora-sep-userspace
Source0: https://github.com/aurora-silicon/aurora-sep-userspace/archive/%{commit}/%{name}-%{commit}.tar.gz
ExclusiveArch: aarch64
BuildRequires: gcc make pkgconf-pkg-config json-c-devel
BuildRequires: python3-devel python3-cryptography
BuildRequires: systemd-rpm-macros
# /dev/sep-key interface 2+ (enclave-checked Touch ID keys) comes with the kernel.
Requires: aurora-sep
Requires: python3 python3-cryptography
Requires: systemd-udev
# The "Touch ID to sign in to <site>" notification.
Recommends: libnotify
Recommends: glib2
# Clients: browsers need nothing; these are the command-line tools.
Suggests: fido2-tools pam-u2f

%description
aurora-fidod makes this Mac's Secure Enclave and Touch ID look like a USB
security key to Linux: WebAuthn and passkeys in Firefox and Chromium, SSH
ecdsa-sk keys, pam_u2f and systemd-cryptenroll --fido2-device. Keys live
in the Secure Enclave, which checks the Touch ID match inside every
signature itself: root on this Mac cannot sign without a finger.

It is installed off. Turn it on with `sudo aurora-fido enable` (refused on
a kernel without /dev/sep-key), off with `sudo aurora-fido disable`;
`aurora-fido status` shows the policy and any 0.1 credentials that must be
registered again. See /usr/share/doc/aurora-fido/fido.md.

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
%dir %{_sysconfdir}/aurora-fido
%config(noreplace) %{_sysconfdir}/aurora-fido/aurora-fido.conf

%changelog
* Wed Nov 11 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.2.0-1
- The Secure Enclave decides every approval: keys with an enclave-enforced
  Touch ID access control, no fprintd or polkit check in the daemon, no
  sealed software key store. Credentials made by 0.1 are refused and must
  be registered again (aurora-fido status lists them). hmac-secret needs a
  kernel with /dev/sep-key SEAL/UNSEAL.

* Sun Nov 08 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1.0-1
- Package aurora-sep-userspace's fido/: Touch ID as a FIDO2/U2F security key,
  installed off (preset disable); aurora-fido enable|disable|status;
  per-credential policy as macOS (Touch ID or password by default, Touch ID
  only opt in). Idea by Erik (@erikwb).
