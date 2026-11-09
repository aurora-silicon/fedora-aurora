%global commit 49b1c107a78b422ab404836fe8da8fbb3c04a857
%global shortcommit %{lua:print(string.sub(rpm.expand("%{commit}"), 1, 12))}
%global snapdate 20261109

Name: aurora-speaker-upgrade
Version: 0.1
Release: 0.8.%{snapdate}git%{shortcommit}%{?dist}
Summary: Move the speakers to speakerguardd v2 with this Mac's own tuning
# The vendored installer collector (asahi_firmware) and the AEA range port
# (from macos-firmware-extract) are MIT as well.
License: MIT
URL: https://github.com/aurora-silicon/speakerguardd/tree/v2/packaging/upgrade
Source0: aurora-speaker-upgrade-%{commit}.tar.gz
Source1: 50-aurora-speaker-upgrade.preset
BuildArch: noarch
BuildRequires: make systemd-rpm-macros python3 python3-cryptography lzfse-libs
Requires: python3 python3-cryptography lzfse-libs util-linux alsa-utils systemd
# The switch needs speakerguardd v2; without it the tool refuses and the
# legacy protection keeps the speakers.
Recommends: speakerguardd-v2
%{?systemd_requires}

%description
aurora-speaker-upgrade moves an existing install's speakers from the legacy
protection (speakersafetyd, speakerguardd 0.1) to speakerguardd v2 with the
Mac's own tuning, and back (--revert). It collects the installer's tuning
bundle from Linux: from an installer bundle of this unit, the installed
macOS's System volume, Apple's restore image of that build by HTTP ranges, or
a collection made on macOS. It stores the bundle root-only, lets v2's silent
self-check prove it, and switches the kernel's speaker interface only on a
pass. The legacy stack stays installed. The service ships disabled.

%prep
%autosetup -n speakerguardd-%{commit}

%build

%check
python3 -I -m unittest discover -s packaging/upgrade/tests

%install
%make_install -C packaging/upgrade PREFIX=%{_prefix} UNITDIR=%{_unitdir} V2UNIT=speakerguardd-v2.service
install -Dm644 %{SOURCE1} %{buildroot}%{_presetdir}/50-aurora-speaker-upgrade.preset

%post
%systemd_post aurora-speaker-upgrade.service

%preun
%systemd_preun aurora-speaker-upgrade.service

%postun
%systemd_postun aurora-speaker-upgrade.service

%files
%license LICENSE
%doc packaging/upgrade/README.md
%{_bindir}/aurora-speaker-upgrade
%{_prefix}/lib/aurora-speaker-upgrade/
%{_datadir}/aurora-speaker-upgrade/restore-images.json
%{_unitdir}/aurora-speaker-upgrade.service
%{_presetdir}/50-aurora-speaker-upgrade.preset
%dir %{_unitdir}/speakerguardd-v2.service.d
%{_unitdir}/speakerguardd-v2.service.d/50-aurora-speaker-upgrade.conf

%changelog
* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.8.20261109git49b1c107a78b
- Enable aurora-speaker-upgrade.service by preset: the next boot moves the
  speakers to speakerguardd v2 when this Mac's own tuning passes the silent
  self-check; a refused Mac keeps speakersafetyd.

* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.7.20261109git49b1c107a78b
- Release candidate 9 (speakerguardd#144): aurora-speaker-upgrade switches
  without the preview confirmation, and the boot unit no longer needs
  --i-understand-preview (still accepted, no effect). The package
  description drops the preview notice.

* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.6.20261109gitff88f9f98070
- Release candidate 8.4 (speakerguardd#143): the supervisor's own hang
  watch no longer counts a system sleep, so a sleep entered without the
  sleep unit (a direct write to /sys/power/state) cannot get it killed at
  the thaw; systemd's watchdog stays as a 10 minute last resort. Also the
  voicing parity updates merged since 8.3.

* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.5.20261109gita561b6fbcf59
- Release candidate 8.3 (speakerguardd#142): before any switch,
  aurora-speaker-upgrade says that speakerguardd v2 is a preview, asks for
  confirmation in a terminal, and needs --i-understand-preview when it runs
  without one (otherwise exit 2, nothing changed).

* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.4.20261109git65064d88a201
- Release candidate 8.2 (speakerguardd#134): a switch in the running boot
  grants at once (the upgrade's umask no longer makes v2's /run graph state
  unreadable to the seat user, which left the speakers silent until a
  reboot); the MacBook Neo's speaker PCM wakes on period interrupts (#133);
  voicing parity #129/#135.

* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.3.20261109git416b1f513b9d
- Release candidate 8.1 (speakerguardd#131): the legacy units' gate runs
  privileged (speakersafetyd is a DynamicUser and could not read the upgrade's
  root-only setting, so a switched Mac started speakersafetyd, which held the
  sense PCM v2 needs: no speakers until reboot); a switched Mac gets the older
  daemons only on a stable refusal; --revert starts only the sense PCM's own
  unit; --check works on dual-interface kernels before the first switch.

* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.2.20261109gitf4bb2fdb4406
- speakerguardd v2 release candidate 8: the dual-interface kernel's lease
  (hardware record before verify; --revert hands the session back to the
  distribution's speaker graph), and the boot unit records a refusal instead
  of retrying it at every boot (exit 1 is an outcome). Still ships disabled.

* Mon Nov 09 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1-0.1
- First preview: routes 0-3, root-only store, v2 self-check gate,
  interface switch, --revert. Ships disabled.
