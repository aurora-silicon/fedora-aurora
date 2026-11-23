%global commit b7013b95052db8265b28feec22793254fe0f3d2b
Name:           aurora-sep-host-state
Version:        1
Release:        1%{?dist}
Summary:        Recover a SEP host-state store that a power cut left short

License:        MIT
URL:            https://github.com/aurora-silicon/aurora-sep-userspace
Source0:        aurora-sep-host-state-%{commit}.tar.gz
BuildArch:      noarch

BuildRequires:  make
BuildRequires:  python3
BuildRequires:  systemd-rpm-macros
Requires:       python3
%{?systemd_requires}

%description
A power cut while the apple_sep driver writes
/var/lib/aurora-sep-host-state.bin can leave a prefix of the file. The driver
refuses any size but the full store and does not reinitialise it, because the
prefix may be the only copy of the host state, so Touch ID stays dead until
the file is recovered by hand.

aurora-sep-host-state-repair.service runs before aurora-sep.service whenever
the store exists. A whole store costs one stat and is never read. A short
prefix whose superblock validates and whose used slots all end inside the
file is backed up to /var/lib/aurora-sep-quarantine and zero-extended back to
full size; anything else is backed up there and removed, so the driver
creates a fresh store.

%prep
%autosetup -n aurora-sep-userspace-%{commit}

%build
%make_build -C host-state LIBEXECDIR=%{_libexecdir}

%check
make -C host-state check PYTHON=%{python3}

%install
make -C host-state install DESTDIR=%{buildroot} PREFIX=%{_prefix} \
    LIBEXECDIR=%{_libexecdir} UNITDIR=%{_unitdir} PRESETDIR=%{_presetdir} \
    DOCDIR=%{_docdir}/%{name}

%post
%systemd_post aurora-sep-host-state-repair.service

%preun
%systemd_preun aurora-sep-host-state-repair.service

%postun
%systemd_postun aurora-sep-host-state-repair.service

%files
%license LICENSES/MIT.txt
%doc %{_docdir}/%{name}/README.md
%{_libexecdir}/aurora-sep-host-state-repair
%{_unitdir}/aurora-sep-host-state-repair.service
%{_presetdir}/90-aurora-sep-host-state-repair.preset

%changelog
* Sat Nov 21 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-1
- First package: aurora-sep-userspace host-state/ at b7013b95
  (aurora-sep-userspace#36 by sioodmy), the same recovery nixos-aurora#313
  ships.
