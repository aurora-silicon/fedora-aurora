%global commit 80b02063f3d87c5c82e38af456f5ef9d043a1a13
%global shortcommit %{lua:print(string.sub(rpm.expand("%{commit}"), 1, 12))}
%global snapdate 20261124

Name: aurora-speaker-upgrade
Version: 0.1
Release: 0.22.%{snapdate}git%{shortcommit}%{?dist}
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
pass. The legacy stack stays installed and keeps any Mac whose self-check
refuses. The service is enabled by preset.

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

%changelog
* Tue Nov 24 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.22.20261124git80b02063f3d8
- Rebuilt from speakerguardd main 80b02063 with speakerguardd-v2
  (speakerguardd#239 to #244). speakerguardd#240: the boot unit judges the
  playback record strictly and per unit.

* Mon Nov 23 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.21.20261123git9b7285c420a7
- Rebuilt from speakerguardd main 9b7285c4 with speakerguardd-v2
  (speakerguardd#200, #228, #229, #231, #232, #234, #236, #238).
- speakerguardd#238: the boot unit moves a speaker to v2 only when
  protected playback rows (a loud step and a thermal ramp) are on record
  for it in speakerguardd-v2's gate data; otherwise it leaves the speakers
  as they are, collects nothing and records no refusal. `run` by hand is
  unchanged, `status` shows boot_migration, and a new row retries a Mac
  the boot unit refused.

* Sat Nov 21 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.20.20261121git29263b5cfa8d
- Rebuilt from speakerguardd main 29263b5c with speakerguardd-v2: the
  self-check it relies on refuses V/I sense that a bit-clock misframe
  corrupts (speakerguardd#225), and a pass is bound to the speaker card's
  device-tree node and the sound modules' build IDs, so a changed audio
  stack runs the switch test again (#226). No change to the tool itself.

* Fri Nov 20 2026 Diljit Singh <hey@djdev.me> - 0.1-0.19.20261120gitf573f6054011
- Rebuilt from speakerguardd main f573f605: a collection that carries the
  installer collector's buzzkill_quadrature record, which speakerguardd v2
  does not read yet, is stored without it instead of being refused
  (speakerguardd#213); reverting to a v2-only kernel restarts the
  supervisor when its own wants link starts it (#215); the
  speakerguardd-v2.service drop-in is gone, as the supervisor unit applies
  the kernel interface itself (#205).

* Fri Nov 20 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1-0.18.20261120gitdafc508877e3
- Enable aurora-speaker-upgrade.service by preset: at the next boot each
  Mac moves its speakers to speakerguardd v2 when its own tuning passes the
  silent self-check; a refused Mac keeps speakersafetyd and is not retried
  until the kernel, speakerguardd or the tool changes.
- Rebuilt from speakerguardd 1.0.0-alpha.2 (main dafc5088).

* Tue Nov 17 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.16.20261117gitbbd9ed30ac43
- Release candidate 9 (speakerguardd#144): switch without the preview
  confirmation; --i-understand-preview is still accepted and has no effect.
- speakerguardd#186: directories this tool creates are 0755 whatever its
  umask, so /etc/speakerguardd stays readable for the seat user.

* Fri Nov 13 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.15.20261113git04169c447065
- Rebuilt from speakerguardd 04169c44 (no change to this tool).

* Fri Nov 13 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.14.20261113git26b88eac71bf
- speakerguardd#159: when the boot chain gives no speaker ID for an AID
  that selects its tuning by speaker ID, go on to the macOS collection
  (route 3), which records the ID, instead of stopping.

* Thu Nov 12 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.13.20261112git836a0efa19fc
- Rebuilt from speakerguardd#167 (no change to this tool).

* Thu Nov 12 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.12.20261112git26db27188637
- Follow speakerguardd-v2 to 26db2718 (speakerguardd#165, #166): the
  parity attestations match the current voicing law again, and verify
  gates every tuning at volume sliders 0.7, 0.46 and 0.25.

* Thu Nov 12 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.11.20261112gitdda9784b09bc
- speakerguardd#163: the seat user's PipeWire, WirePlumber and
  pipewire-pulse stop before the speaker interface switches and start
  again after it, on a switch and on a rollback. A unit still stopping
  15 s after SIGTERM is killed, so a busy WirePlumber no longer runs the
  session restart past its time limit. Also the installer collector from
  aurora-installer de37d8eb (speakerguardd#157).

* Wed Nov 11 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.10.20261111gitea73fdf0eebc
- Release candidate 8.8 (speakerguardd#153-#156 on top of RC8.7): the
  speakers' volume is kept across graph restarts and a first start begins
  at 30 % instead of 100 %; the first start after the switch test no
  longer waits 60 s; lsm2 applies MaxTemperatureAttenuation as macOS does.
  v2 stays a preview and opt-in.

* Wed Nov 11 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.9.20261111git24451b6f817d
- Release candidate 8.7 (speakerguardd#149): with nothing playing the
  speaker path powers down (amps and sense unlinked, both PCMs closed, the
  grant given back), as macOS does: about 1 W less at idle on a MacBook Air
  M2, 0.4 W on a MacBook Pro M1 Pro. The stream that wakes the speakers
  loses nothing: its first frames are held until the amps play, then
  played in order. The self-check's graph step accounts for the sink
  starting again with each first stream. v2 stays a preview and opt-in.

* Tue Nov 10 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.8.20261110gitd69f0115edc1
- Release candidate 8.6, a bug-fix release (speakerguardd#151, #152,
  #148): after a system sleep the supervisor waits for the engine to beat
  steadily before granting, and the first grant rides out the sink's
  reopen, so the speakers no longer go silent until a restart after a
  resume (M1 Pro); the supervisor's hang watch tells a frozen process
  from a hung loop and no longer restarts it after a freeze with the
  clocks running; 'run' checks that v2 really holds the speakers before
  saying there is nothing to do. Also #108, #109 (finding the MCA and the
  speaker card) and #150 (no CPU frequency floor for the pollers). v2
  stays a preview and opt-in.

* Tue Nov 10 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.7.20261110gitf3ceaa2d768a
- Release candidate 8.5, a bug-fix release (speakerguardd#145, #146):
  --check on a Mac that speakerguardd v2 already protects no longer takes
  the speakers from it (it left them at the kernel floor until a reboot),
  and a same-boot --revert lets the session open the speaker before it
  starts the legacy daemon (speakersafetyd could fail to open the sense
  PCM and restart). v2 stays a preview and opt-in.

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
