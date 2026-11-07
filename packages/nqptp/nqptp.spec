%global commit ab8fb67483411640fd7f1e193889482f2421c37c
# Aurora 2026-10-25: nqptp for the AirPlay 2 receivers (Shairport Sync 4.3.7 with AirPlay 2).
# Fedora does not package nqptp. Source is the upstream 1.2.9 tag tarball, with one Aurora patch.
Name:           nqptp
Version:        1.2.9
Release:        1%{?dist}.aurora4
Summary:        Not Quite PTP: PTP timing companion for Shairport Sync's AirPlay 2 mode
License:        GPL-2.0-only
URL:            https://github.com/mikebrady/nqptp
# Upstream tag 1.2.9 (ab8fb6748341), pinned in sources.json.
Source0:        nqptp-%{commit}.tar.gz
# Layout check, same numbers as shairport-sync-4.3.7-nqptp-smi11.patch asserts.
Source1:        nqptp-smi11-layout-check.c
# Aurora: block in select() instead of polling every 10 ms. Upstream wakes its
# SCHED_FIFO thread 100 times a second with no AirPlay session; on the J616s
# (M4 Pro) that held a P cluster at its top state ~22 % of the time and cost
# 1.37 W at idle (2026-10-31 A/B, aurora-ctl t-3690 follow-up).
Patch0:         nqptp-1.2.9-idle-wakeups.patch

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  pkgconfig(systemd)
BuildRequires:  systemd-rpm-macros
%{?systemd_requires}
# Shairport Sync's AirPlay 2 mode needs this exact shared memory interface version.
Provides:       nqptp(smi) = 11

%description
NQPTP ("Not Quite PTP") listens to the PTP (IEEE 1588) timing traffic of AirPlay 2
senders and players on UDP ports 319 and 320 and publishes the selected clock to
Shairport Sync through POSIX shared memory. Shairport Sync's AirPlay 2 mode needs
it for timing and for synchronised multi-room playback.

The unit is upstream's: a systemd DynamicUser with only CAP_NET_BIND_SERVICE
(for ports 319 and 320) as an ambient capability, not root.

%prep
%autosetup -n nqptp-%{commit} -p1

%build
autoreconf -fi
%configure --with-systemd-startup --with-systemdsystemunitdir=%{_unitdir}
%make_build

%install
%make_install
# upstream installs the unit only if one is not there already; make sure it landed
test -f %{buildroot}%{_unitdir}/nqptp.service

%check
grep -q '^DynamicUser=yes$' %{buildroot}%{_unitdir}/nqptp.service
grep -q '^AmbientCapabilities=CAP_NET_BIND_SERVICE$' %{buildroot}%{_unitdir}/nqptp.service
grep -q '^ExecStart=%{_bindir}/nqptp$' %{buildroot}%{_unitdir}/nqptp.service
%{__cc} %{optflags} -std=gnu11 -I. -o smi11-layout-check %{SOURCE1}
./smi11-layout-check
%{buildroot}%{_bindir}/nqptp -V | grep -F 'Version: %{version}. Shared Memory Interface Version: smi11.'

%post
%systemd_post nqptp.service

%preun
%systemd_preun nqptp.service

%postun
# No restart on upgrade: nqptp unlinks its shared memory on exit, and a running
# Shairport Sync keeps the old mapping, so restart both together by hand.
%systemd_postun nqptp.service

%files
%license LICENSE
%doc README.md RELEASE_NOTES.md
%{_bindir}/nqptp
%{_mandir}/man8/nqptp.8*
%{_unitdir}/nqptp.service

%changelog
* Tue Nov 03 2026 Aurora Silicon <noreply@aurorasilicon.org> - 1.2.9-1.aurora4
- Build in fedora-aurora for Fedora 44 and 45 (the receivers ran local aurora3 builds)
- Vendor comes from the shared builder

* Sat Oct 31 2026 Aurora Silicon <noreply@aurorasilicon.org> - 1.2.9-1.aurora3
- Block in select() until a timed task has work to do (no 100 Hz idle wakeups)

* Sun Oct 25 2026 Aurora Silicon <noreply@aurorasilicon.org> - 1.2.9-1.aurora2
- Vendor: Aurora Silicon

* Sun Oct 25 2026 Aurora Silicon <noreply@aurorasilicon.org> - 1.2.9-1.aurora1
- First package, upstream tag 1.2.9 (smi11), upstream unit
