%global commit fb19f69381ad29cd51a06dda7456ce6c01030a12
Name:           aurora-touchid-rearm
Version:        1
Release:        3%{?dist}
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

/etc/aurora/touchid.conf chooses Touch ID after a restart: from the first
login (the default), or, as on macOS, only after the first password since
boot (require_password_after_boot = yes, set by aurora-touchid-boot.service).

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
    SYSCONFDIR=%{_sysconfdir} DOCDIR=%{_docdir}/%{name}
install -d %{buildroot}%{_presetdir}
printf 'enable aurora-touchid-rearm.socket\nenable aurora-touchid-boot.service\n' >%{buildroot}%{_presetdir}/80-aurora-touchid-rearm.preset

%post
%systemd_post aurora-touchid-rearm.socket aurora-touchid-boot.service

%posttrans
# Listen now, not only after the next boot: the PAM line is already in place.
if [ -d /run/systemd/system ] && systemctl -q is-enabled aurora-touchid-rearm.socket 2>/dev/null; then
    systemctl start aurora-touchid-rearm.socket >/dev/null 2>&1 || :
fi

%preun
%systemd_preun aurora-touchid-rearm.socket aurora-touchid-boot.service

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
%{_unitdir}/aurora-touchid-boot.service
%dir %{_sysconfdir}/aurora
%config(noreplace) %{_sysconfdir}/aurora/touchid.conf
%{_presetdir}/80-aurora-touchid-rearm.preset

%changelog
* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-3
- Touch ID after a restart is a setting: /etc/aurora/touchid.conf,
  require_password_after_boot = no (default) or yes (as on macOS), applied
  by aurora-touchid-boot.service

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-2
- Count every root-side password and clear pending failed matches, when the
  driver says its re-arm never waits for a capture

* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-1
- First package
