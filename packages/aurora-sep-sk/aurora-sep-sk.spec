%global commit 72eaf547174745b9c1e008faeeaa1e98b80bc310
Name: aurora-sep-sk
Version: 0.1.0
Release: 1%{?dist}
Summary: OpenSSH security-key provider for Secure Enclave keys
License: MIT
URL: https://github.com/aurora-silicon/aurora-sep-userspace
Source0: https://github.com/aurora-silicon/aurora-sep-userspace/archive/%{commit}/%{name}-%{commit}.tar.gz
ExclusiveArch: aarch64
BuildRequires: gcc make pkgconf-pkg-config openssl-devel binutils
BuildRequires: openssh-clients git-core
BuildRequires: systemd-rpm-macros
Requires: aurora-sep
Requires: openssh-clients
Requires: systemd-udev

%description
libaurora-sep-sk.so is an OpenSSH security-key provider. It makes ecdsa-sk
keys whose private key is created inside this Mac's Secure Enclave and never
leaves it: ssh logins, ssh-keygen -Y signatures and git commit signing.
Keys made with a Touch ID policy sign only after a Touch ID match that the
Secure Enclave itself checks.

It needs a kernel with /dev/sep-key. The package gives the sep-key group
access to it; add a user with `sudo usermod -aG sep-key USER`, then use
`ssh-keygen -t ecdsa-sk -w %{_libdir}/libaurora-sep-sk.so`. See
%{_docdir}/%{name}/ssh-sk.md.

%prep
%autosetup -n aurora-sep-userspace-%{commit}

%build
%make_build -C sk CFLAGS="%{optflags}" LDFLAGS="%{build_ldflags}"

%check
# OpenSSH flow against a test build in which software P-256 keys stand in
# for the enclave: no root, no hardware.
make -C sk check CFLAGS="%{optflags}"

%install
%make_install -C sk PREFIX=%{_prefix} LIBDIR=%{_libdir} \
	UDEVRULESDIR=%{_udevrulesdir} SYSUSERSDIR=%{_sysusersdir}
install -Dm644 docs/ssh-sk.md %{buildroot}%{_docdir}/%{name}/ssh-sk.md

%post
%udev_rules_update
# Give an existing /dev/sep-key its group now, not at the next boot.
udevadm trigger --action=change --subsystem-match=misc --sysname-match=sep-key >/dev/null 2>&1 || :

%postun
%udev_rules_update

%files
%license LICENSES/MIT.txt
%doc %{_docdir}/%{name}/ssh-sk.md
%{_libdir}/libaurora-sep-sk.so
%{_udevrulesdir}/70-aurora-sep-key.rules
%{_sysusersdir}/aurora-sep-key.conf

%changelog
* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1.0-1
- Package aurora-sep-userspace's sk/: OpenSSH ecdsa-sk keys in the Secure
  Enclave, with the sep-key group udev rule and its sysusers entry.
