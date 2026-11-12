%global commit a343f3309ce7aa6eaa0b2dc89af59da425fdd1f9
Name: aurora-diag
Version: 0.4.0
Release: 1%{?dist}
Summary: Bring-up diagnostics for Apple silicon Macs (development only)
License: MIT
URL: https://github.com/aurora-silicon/aurora-diag
Source0: aurora-diag-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: make python3
Requires: python3
Recommends: python3-textual
Recommends: alsa-utils
Recommends: vulkan-tools
Recommends: mesa-demos
Recommends: iw
Recommends: smartmontools
Recommends: bluez
Recommends: glib2

%description
Shows every sensor, clock, hardware block, service and GPU API (Vulkan,
OpenGL, GLES) on Apple silicon Macs, says what works and what does not,
changes what may be changed with a journal and automatic restore, and
gives a fast pass/warn/fail check plus snapshots and diffs to confirm a
new kernel did not regress. aurora-panic-log shows the last panic iBoot
kept for the next OS. Development and bring-up tool: not installed by
default.

%prep
%autosetup -n aurora-diag-%{commit}

%build

%check
make check

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%files
%license LICENSE
%doc %{_docdir}/aurora-diag
%{_bindir}/aurora-diag
%{_bindir}/aurora-panic-log
%{_datadir}/aurora-diag
%{_datadir}/applications/org.aurorasilicon.Diag.desktop

%changelog
* Thu Nov 12 2026 Aurora Silicon <ryan@aurorasilicon.org> - 0.4.0-1
- Initial package: aurora-diag 0.4.0 and aurora-panic-log, opt-in.
