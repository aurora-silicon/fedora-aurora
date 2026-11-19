%global commit a434eed14c7ec408a27c988b338294772fd473de
Name: speakerguardd
Version: 0.1.12
Release: 5%{?dist}
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
%autosetup -n speakerguardd-a434eed14c7ec408a27c988b338294772fd473de

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
# One instance per card (speakerguardd@AppleJ700.service), pulled in by the
# udev rule for every macaudio card; its start condition runs it only for a
# card with a profile here and none from speakersafetyd.
install -Dm644 speakerguardd@.service %{buildroot}%{_unitdir}/speakerguardd@.service
grep -qx 'ExecCondition=/usr/bin/speakerguardd -c /usr/share/speakerguardd -C %%I --owns-card' %{buildroot}%{_unitdir}/speakerguardd@.service
grep -qx 'ExecStart=/usr/bin/speakerguardd -c /usr/share/speakerguardd -C %%I --wait-for-card 30' %{buildroot}%{_unitdir}/speakerguardd@.service
install -Dm644 95-speakerguardd.rules %{buildroot}%{_udevrulesdir}/95-speakerguardd.rules
install -Dm755 %{SOURCE1} %{buildroot}%{_libexecdir}/speakerguardd/use-feedback-guard
install -Dm644 %{SOURCE2} %{buildroot}%{_unitdir}/speakersafetyd.service.d/50-j700-guard.conf

%post
%systemd_post speakerguardd@.service
# The systemd macros take unit names, not patterns: hand them the card
# instances that are loaded now.
%preun
%systemd_preun speakerguardd@.service
if [ $1 -eq 0 ] && [ -x /usr/lib/systemd/systemd-update-helper ]; then
    units=$(systemctl list-units --all --plain --no-legend 'speakerguardd@*.service' 2>/dev/null | awk '{print $1}')
    [ -z "$units" ] || /usr/lib/systemd/systemd-update-helper remove-system-units $units || :
fi
%postun
if [ $1 -ge 1 ] && [ -x /usr/lib/systemd/systemd-update-helper ]; then
    units=$(systemctl list-units --plain --no-legend 'speakerguardd@*.service' 2>/dev/null | awk '{print $1}')
    [ -z "$units" ] || /usr/lib/systemd/systemd-update-helper mark-restart-system-units $units || :
fi

%files
%license LICENSE
%{_bindir}/speakerguardd
%{_datadir}/speakerguardd/
%{_unitdir}/speakerguardd@.service
%{_unitdir}/speakersafetyd.service.d/50-j700-guard.conf
%{_udevrulesdir}/95-speakerguardd.rules
%{_libexecdir}/speakerguardd/

%changelog
* Thu Nov 19 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1.12-5
- Pin speakerguardd a434eed14c7e (speakerguardd#197): the unit is the
  template speakerguardd@.service, one instance per card id, started by
  udev for every macaudio card and run only for a card with a profile here
  and none from speakersafetyd. The -C AppleJ700 edit of the unit is gone.
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.12-4
- Pin speakerguardd main 0287029648842 (pull 29 merged, safety review
  approved): the evidence start, with its marker at
  /run/speakerguardd.unlocked.
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.12-3.evidence
- Pin speakerguardd pull 29 at 2137581b706a: the evidence start is refused
  after any unlock this boot (a /run marker carrying the boot id, and no
  unlock without the /run state written), and under a speakersafetyd flag
  or a macaudio override of the safe level.
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.12-2.evidence
- Pin speakerguardd pull 29 (ef36a2617148): start each boot from evidence
  (a protected-past bound and the last run's record) instead of latched at
  the coils' limit; the Neo plays at full level from the first sound.
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
