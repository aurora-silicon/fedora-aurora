%global commit 34aeed9085ad0f66cb8f266f997e11dd781470a6
Name: speakerguardd
Version: 0.1.12
Release: 1%{?dist}
Summary: Feed-forward speaker protection for Apple J700
License: MIT
URL: https://github.com/aurora-silicon/speakerguardd
Source0: speakerguardd-%{commit}.tar.gz
Source1: use-feedback-guard
Source2: 50-j700-guard.conf
ExclusiveArch: aarch64
BuildRequires: rust cargo alsa-lib-devel pkgconf-pkg-config systemd-rpm-macros

%description
Feed-forward speaker protection for Apple J700. Built from the recorded Aurora source revision.

%prep
%autosetup -n speakerguardd-34aeed9085ad0f66cb8f266f997e11dd781470a6

%build
# The binary names its source in -V and the journal.
export SPEAKERGUARDD_COMMIT=%(echo %{commit} | cut -c1-12)
cargo build --locked --release

%check
cargo test --locked

%install
install -Dm755 target/release/speakerguardd %{buildroot}%{_bindir}/speakerguardd
mkdir -p %{buildroot}%{_datadir}/speakerguardd
cp -a conf/. %{buildroot}%{_datadir}/speakerguardd/
install -Dm644 speakerguardd.service %{buildroot}%{_unitdir}/speakerguardd.service
sed -i 's@ExecStart=/usr/bin/speakerguardd -c /usr/share/speakerguardd@ExecStart=/usr/bin/speakerguardd -c /usr/share/speakerguardd -C AppleJ700@' %{buildroot}%{_unitdir}/speakerguardd.service
# The J700 model must be the one the unit names.
grep -qx 'ExecStart=/usr/bin/speakerguardd -c /usr/share/speakerguardd -C AppleJ700 --wait-for-card 30' %{buildroot}%{_unitdir}/speakerguardd.service
install -Dm644 95-speakerguardd.rules %{buildroot}%{_udevrulesdir}/95-speakerguardd.rules
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

%changelog
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
