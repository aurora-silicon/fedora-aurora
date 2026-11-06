%global commit f73bf267eed958d47a63a7a49c46e669d70f5c75
Name:           aurora-touchid-rearm
Version:        1
Release:        1%{?dist}
Summary:        Re-arm Touch ID with the password after a lockout

License:        GPL-2.0-only
URL:            https://github.com/aurora-silicon/aurora-sep-userspace
Source0:        aurora-touchid-rearm-%{commit}.tar.gz

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  pam-devel
BuildRequires:  python3
BuildRequires:  systemd-rpm-macros
Requires:       pam
# The labels and the domain are in the aurora_sep module.
Requires:       (aurora-sep-selinux >= 1-20 if selinux-policy-targeted)
%{?systemd_requires}

%description
After too many failed matches the Secure Enclave stops matching, and the
apple_sep driver refuses Touch ID until the password is used, as macOS does.
pam_aurora_touchid runs straight after pam_unix accepts a password and hands
it to aurora-touchid-rearm, a socket-activated root service that checks the
caller, the enrolled fingerprints and the password again before it asks the
driver to re-arm Touch ID. A fingerprint never re-arms it.

%prep
%autosetup -n aurora-sep-userspace-%{commit}

%build
%make_build -C touchid-rearm CFLAGS="%{optflags}" LDFLAGS="%{build_ldflags}" WARN="-Wall -Wextra"

%check
make -C touchid-rearm check CFLAGS="%{optflags}" WARN="-Wall -Wextra"

%install
make -C touchid-rearm install DESTDIR=%{buildroot} \
    LIBEXECDIR=%{_libexecdir} PAMDIR=%{_libdir}/security \
    PAMCONFDIR=%{_prefix}/lib/pam.d UNITDIR=%{_unitdir} \
    DOCDIR=%{_docdir}/%{name}
install -d %{buildroot}%{_presetdir}
echo 'enable aurora-touchid-rearm.socket' >%{buildroot}%{_presetdir}/80-aurora-touchid-rearm.preset

%post
%systemd_post aurora-touchid-rearm.socket

%posttrans
# Listen now, not only after the next boot: the PAM line is already in place.
if [ -d /run/systemd/system ] && systemctl -q is-enabled aurora-touchid-rearm.socket 2>/dev/null; then
    systemctl start aurora-touchid-rearm.socket >/dev/null 2>&1 || :
fi

%preun
%systemd_preun aurora-touchid-rearm.socket

%postun
%systemd_postun_with_restart aurora-touchid-rearm.socket

%files
%license LICENSES/GPL-2.0-only.txt
%doc %{_docdir}/%{name}/README.md
%{_libexecdir}/aurora-touchid-rearm
%{_libdir}/security/pam_aurora_touchid.so
%{_prefix}/lib/pam.d/aurora-touchid-rearm
%{_unitdir}/aurora-touchid-rearm.socket
%{_unitdir}/aurora-touchid-rearm@.service
%{_presetdir}/80-aurora-touchid-rearm.preset

%changelog
* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-1
- First package
