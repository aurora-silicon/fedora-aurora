%global commit 191de3c9b24ab00d98f545ac546a09cc83af00b6
Name: speakerguardd
Version: 0.1.13~rc1
Release: 1%{?dist}
Summary: Unified Apple speaker protection release candidate
License: MIT
URL: https://github.com/aurora-silicon/speakerguardd
Source0: speakerguardd-%{commit}.tar.gz
Source1: use-feedback-guard
Source2: 50-j700-guard.conf
ExclusiveArch: aarch64
BuildRequires: rust cargo alsa-lib-devel pkgconf-pkg-config systemd-rpm-macros gcc make ladspa-devel python3

Requires: python3

%description
Unified Apple speaker protection candidate. Unqualified profiles still require
explicit admission. This draft must pass the upstream release gates before use.

%package xlim
Summary: Optional speaker excursion and peak limiter
%description xlim
Optional LADSPA excursion limiter. Installing it does not enable an audio graph.

%prep
%autosetup -n speakerguardd-191de3c9b24ab00d98f545ac546a09cc83af00b6

%build
# The binary names its source in -V and the journal.
export SPEAKERGUARDD_COMMIT=%(echo %{commit} | cut -c1-12)
cargo build --locked --release -j8
make -j8 filter

%check
cargo test --locked --release -j8
python3 tools/test-preserve-recordings.py
make -j8 filter-test

%install
install -Dm755 target/release/speakerguardd %{buildroot}%{_bindir}/speakerguardd
mkdir -p %{buildroot}%{_datadir}/speakerguardd
cp -a conf/. %{buildroot}%{_datadir}/speakerguardd/
install -Dm644 speakerguardd.service %{buildroot}%{_unitdir}/speakerguardd.service
# Keep upstream DT/ALSA profile selection and its qualification refusal.
grep -qx 'ExecStart=/usr/bin/speakerguardd' %{buildroot}%{_unitdir}/speakerguardd.service
install -Dm644 95-speakerguardd.rules %{buildroot}%{_udevrulesdir}/95-speakerguardd.rules
install -Dm755 tools/preserve-recordings %{buildroot}%{_libexecdir}/speakerguardd/preserve-recordings
install -Dm755 filter/speakerguard-xlim.so %{buildroot}%{_libdir}/ladspa/speakerguard-xlim.so
install -Dm755 %{SOURCE1} %{buildroot}%{_libexecdir}/speakerguardd/use-feedback-guard
install -Dm644 %{SOURCE2} %{buildroot}%{_unitdir}/speakersafetyd.service.d/50-j700-guard.conf

%post
%systemd_post speakerguardd.service
%preun
%systemd_preun speakerguardd.service
%postun
%systemd_postun_with_restart speakerguardd.service

%files
%license LICENSE
%{_bindir}/speakerguardd
%{_datadir}/speakerguardd/
%{_unitdir}/speakerguardd.service
%{_unitdir}/speakersafetyd.service.d/50-j700-guard.conf
%{_udevrulesdir}/95-speakerguardd.rules
%{_libexecdir}/speakerguardd/

%files xlim
%license LICENSE
%{_libdir}/ladspa/speakerguard-xlim.so

%changelog
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.13~rc1-1
- Pin the integrated upstream RC; keep failing acceptance gates effective.
- Package restart evidence preservation and the optional xlim plugin.
- Retain upstream profile selection, qualification and service owner policy.
* Fri Oct 30 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.12-1
- Move to speakerguardd 0.1.12 (main 34aeed9), the build the Neo has run
  since 25 October: it fails closed on control errors, lost sense time and
  stale state, waits for the card before taking the interlock, and runs at
  SCHED_FIFO 50 with its pages locked.
- Keep the upstream unit's own start limit (five attempts in 60 s) instead
  of rewriting it, and name the commit in the binary.
* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-3
- Install the J700 guard condition under libexec, so systemd runs it as an
  ordinary service program under SELinux instead of in its own init domain.
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
