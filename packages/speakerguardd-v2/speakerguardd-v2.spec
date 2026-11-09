%global commit 416b1f513b9d9e924d7e4de16385ba19f7364a92
%global shortcommit %{lua:print(string.sub(rpm.expand("%{commit}"), 1, 12))}
%global snapdate 20261109
%global selinuxtype targeted
%global modulename speakerguardd
# The crates this package ships; the rig and benchmark crates stay out.
%global cargo_pkgs -p sgv2-core -p sgv2-lv2 -p sgv2-supervisor -p aurora-speaker-tuning

Name: speakerguardd-v2
Version: 1.0.0~alpha.1
Release: 0.34.%{snapdate}git%{shortcommit}%{?dist}
Summary: In-graph speaker protection for Apple Silicon Macs (speakerguardd 1.0, preview)
# aurora-speaker-tuning is based on aurora-audio-dsp by saku, also MIT.
License: MIT
URL: https://github.com/aurora-silicon/speakerguardd
Source0: speakerguardd-v2-%{commit}.tar.gz
Source2: speakerguardd.fc
Source3: 50-speakerguardd-v2.preset
Source4: README.md
ExclusiveArch: aarch64
BuildRequires: rust >= 1.85
BuildRequires: cargo
BuildRequires: systemd-rpm-macros
BuildRequires: selinux-policy-devel make bzip2
Requires: (%{name}-selinux = %{version}-%{release} if selinux-policy-%{selinuxtype})
Requires: pipewire-module-filter-chain-lv2
# Provisioning, the gate, the self-check and the session helper: Python,
# the ALSA tools (the gate's interface probe and the silent switch test),
# pw-link/pw-dump for the speaker graph, loginctl for the seat user and
# restorecon for the state directory.
Requires: python3 alsa-utils pipewire-utils systemd policycoreutils
# The provisioning marker (speakerguardd#106) hides the speaker card's raw
# ports; aurora-audio 4.1-11 keeps a jack Mac's built-in card on HiFi with
# nothing plugged in, so it must be there first (asahi-audio#24).
Requires: aurora-audio >= 4.1-11
%{?systemd_requires}

%description
speakerguardd 1.0 is a new speaker protection stack that works the way
macOS's does: the protection unit runs inside the PipeWire speaker graph as
an LV2 plugin, with the amplifier's voltage and current sense as its second
input where the Mac has it, driven by that Mac's own tuning bundle.

It ships the supervisor, provisioning (the parameter blob compiled from the
Mac's tuning, the seat user, the configuration, the speaker graph), the
first-boot wiring self-check, the session helper, the sgv2 LV2 bundle and the
aurora-speaker-tuning reader. It installs on every Mac beside speakerguardd
0.1 and speakersafetyd, and the fleet gate picks one stack per boot: v2 on a
board gated for it whose kernel has the v2 interface, the older daemons
everywhere else. The kernel is the switch: a fleet kernel without the
interface keeps every Mac on the older daemons.

%package selinux
Summary: SELinux policy module for speakerguardd 1.0
BuildArch: noarch
Requires: selinux-policy-%{selinuxtype}
Requires(post): selinux-policy-%{selinuxtype}
Requires(post): policycoreutils
Requires(postun): libselinux-utils policycoreutils
%{?selinux_requires}

%description selinux
Confines the speakerguardd 1.0 supervisor in its own domain, speakerguardd_t,
and labels its program, its runtime directory, where it publishes the
plugin's parameters and engine page, and its state directory, where
provisioning and the self-check keep the parameter blob and their records.

%prep
%autosetup -n speakerguardd-%{commit}
# The policy module is upstream's (packaging/selinux); the file contexts are
# this package's, for the paths it installs to.
cp -p packaging/selinux/%{modulename}.te .
# The kernel's "Speaker Protection" lock and lease writes need CAP_SYS_ADMIN
# (-EPERM otherwise): the policy must grant it to the supervisor's domain.
grep -qx 'allow speakerguardd_t self:capability sys_admin;' %{modulename}.te
cp -p %{SOURCE2} .
cp -p %{SOURCE4} README.packaging.md

%build
cargo build --locked --release %{cargo_pkgs}
%make_build -f %{_datadir}/selinux/devel/Makefile %{modulename}.pp
bzip2 -9 %{modulename}.pp

%check
cargo test --locked --release %{cargo_pkgs}
python3 -I packaging/session/test_provision.py

%install
install -Dm755 target/release/speakerguardd %{buildroot}%{_libexecdir}/speakerguardd-v2/speakerguardd
install -Dm755 target/release/aurora-speaker-tuning %{buildroot}%{_bindir}/aurora-speaker-tuning
install -d %{buildroot}%{_libdir}/lv2/sgv2.lv2
install -pm644 crates/sgv2-lv2/lv2/sgv2.lv2/*.ttl %{buildroot}%{_libdir}/lv2/sgv2.lv2/
install -pm755 target/release/libsgv2_lv2.so %{buildroot}%{_libdir}/lv2/sgv2.lv2/libsgv2_lv2.so
# Every plugin the bundle names must be the library installed beside it.
if grep -ho 'lv2:binary <[^>]*>' %{buildroot}%{_libdir}/lv2/sgv2.lv2/*.ttl | grep -v '<libsgv2_lv2.so>'; then
    echo 'The sgv2 bundle names a library this package does not install' >&2; exit 1
fi
lx=%{_libexecdir}/speakerguardd-v2
for f in speakerguardd-provision speakerguardd-gate speakerguardd-selfcheck speakerguardd-session; do
    install -Dm755 packaging/session/$f %{buildroot}$lx/$f
done
install -Dm644 packaging/session/wiring.py %{buildroot}$lx/wiring.py
install -Dm644 packaging/session/gen.py %{buildroot}$lx/gen.py
# The macOS parity attestations speakerguardd-selfcheck verify reads.
install -Dm644 packaging/session/parity.json %{buildroot}%{_datadir}/speakerguardd/parity.json
# The fleet gate's data, unchanged from upstream. Every per-board value is
# derived from the Mac's device tree and tuning at run time (wiring.py).
install -Dm644 packaging/session/gate.json %{buildroot}%{_datadir}/speakerguardd/gate.json
# The per-machine graphs, as reference data: provisioning generates the
# machine's own from the self-check's record.
for f in packaging/pipewire/sgv2-*.conf; do
    install -Dpm644 $f %{buildroot}%{_datadir}/speakerguardd/pipewire/$(basename $f)
done
for f in packaging/wireplumber/60-sgv2-*.conf; do
    install -Dpm644 $f %{buildroot}%{_datadir}/speakerguardd/wireplumber/$(basename $f)
done
# The upstream units, under their own names so they install beside the 0.1
# unit, with the programs where this package installs them.
rename_units() {
    sed -e "s@/usr/libexec/speakerguardd/@$lx/@g" -e "s@^ExecStart=/usr/bin/speakerguardd @ExecStart=$lx/speakerguardd @" \
        -e 's@\bspeakerguardd\(-[a-z]\+\)\?\.\(service\|path\)\b@speakerguardd-v2\1.\2@g' "$1"
}
for u in speakerguardd.service speakerguardd-provision.service speakerguardd-selfcheck.service speakerguardd-switchtest.service \
         speakerguardd-seat.service speakerguardd-seat.path speakerguardd-session.service speakerguardd-graph.service \
         speakerguardd-sleep.service; do
    rename_units packaging/systemd/$u > ${u/speakerguardd/speakerguardd-v2}
done
# Each rewrite must have taken, and no unit may chain to another daemon.
grep -qx "ExecStart=$lx/speakerguardd \$SGV2_ARGS" speakerguardd-v2.service
grep -qx 'Requires=speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service' speakerguardd-v2.service
grep -q '^After=.*speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service' speakerguardd-v2.service
grep -Eq '^CapabilityBoundingSet=.*\bCAP_SYS_ADMIN\b' speakerguardd-v2.service
# A dual kernel (linux 98cb6a86+): the supervisor's start puts it on the lease.
grep -qx "ExecStartPre=$lx/speakerguardd-gate interface" speakerguardd-v2.service
grep -qx 'Requires=speakerguardd-v2-provision.service' speakerguardd-v2-selfcheck.service
grep -qx 'Before=speakerguardd-v2-selfcheck.service speakerguardd-v2.service' speakerguardd-v2-provision.service
grep -qx "ExecStart=$lx/speakerguardd-provision run" speakerguardd-v2-provision.service
grep -qx "ExecStartPost=$lx/speakerguardd-provision activate --graph-unit speakerguardd-v2-graph.service" speakerguardd-v2-selfcheck.service
# The switch test runs after login (speakerguardd#102), before the supervisor.
grep -qx "ExecStart=$lx/speakerguardd-selfcheck run --defer --params \${SGV2_PARAMS} -- \$SGV2_TUNING" speakerguardd-v2-selfcheck.service
grep -qx 'Requires=speakerguardd-v2-switchtest.service' speakerguardd-v2.service
grep -qx 'After=speakerguardd-v2-switchtest.service' speakerguardd-v2.service
grep -qx 'Requires=speakerguardd-v2-selfcheck.service' speakerguardd-v2-switchtest.service
grep -qx 'After=speakerguardd-v2-selfcheck.service systemd-user-sessions.service' speakerguardd-v2-switchtest.service
grep -qx 'Before=speakerguardd-v2.service' speakerguardd-v2-switchtest.service
grep -qx "ExecCondition=$lx/speakerguardd-selfcheck pending" speakerguardd-v2-switchtest.service
grep -qx "ExecStartPost=$lx/speakerguardd-provision activate --graph-unit speakerguardd-v2-graph.service" speakerguardd-v2-switchtest.service
grep -qx "ExecStopPost=$lx/speakerguardd-selfcheck pending --clear" speakerguardd-v2-switchtest.service
grep -qx "ExecStart=$lx/speakerguardd-provision seat --unit speakerguardd-v2.service" speakerguardd-v2-seat.service
grep -qx 'Unit=speakerguardd-v2-seat.service' speakerguardd-v2-seat.path
grep -qx "ExecCondition=$lx/speakerguardd-provision is-seat" speakerguardd-v2-session.service
grep -q "^ExecStart=$lx/speakerguardd-session " speakerguardd-v2-session.service
grep -qx 'Before=sleep.target' speakerguardd-v2-sleep.service
grep -qx "ExecStart=$lx/speakerguardd-provision sleep --unit speakerguardd-v2.service" speakerguardd-v2-sleep.service
grep -qx "ExecStop=$lx/speakerguardd-provision wake --unit speakerguardd-v2.service" speakerguardd-v2-sleep.service
# The supervisor and sleep hooks need a qualified board (gate v2); provisioning,
# the seat follower and the silent self-check run first, in the gate's prepare
# mode, and produce the records that qualify the board (speakerguardd#96).
for u in speakerguardd-v2.service speakerguardd-v2-sleep.service; do
    grep -qx "ExecCondition=$lx/speakerguardd-gate v2" $u
done
for u in speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service speakerguardd-v2-seat.service; do
    grep -qx "ExecCondition=$lx/speakerguardd-gate prepare" $u
done
if grep -Eq '^(OnFailure|OnSuccess)=|speakersafetyd|=speakerguardd\.service|/usr/libexec/speakerguardd/' speakerguardd-v2*.service speakerguardd-v2*.path; then
    echo 'A speakerguardd 1.0 unit chains to or names another daemon' >&2; exit 1
fi
for u in speakerguardd-v2.service speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service \
         speakerguardd-v2-switchtest.service speakerguardd-v2-seat.service speakerguardd-v2-seat.path speakerguardd-v2-sleep.service; do
    install -Dm644 $u %{buildroot}%{_unitdir}/$u
done
for u in speakerguardd-v2-session.service speakerguardd-v2-graph.service; do
    install -Dm644 $u %{buildroot}%{_userunitdir}/$u
done
# The older daemons start only where v2 does not run and the kernel has no
# v2 interface: exactly one stack holds the speakers on each boot.
sed -e "s@/usr/libexec/speakerguardd/@$lx/@g" packaging/systemd/legacy-gate.conf > legacy-gate.conf
grep -qx "ExecCondition=+$lx/speakerguardd-gate legacy" legacy-gate.conf
for u in speakersafetyd speakerguardd; do
    install -Dm644 legacy-gate.conf %{buildroot}%{_unitdir}/$u.service.d/60-speakerguardd-v2-gate.conf
done
install -Dpm644 %{SOURCE3} %{buildroot}%{_presetdir}/50-speakerguardd-v2.preset
install -d %{buildroot}%{_userpresetdir}
printf 'enable speakerguardd-v2-graph.service\nenable speakerguardd-v2-session.service\n' > %{buildroot}%{_userpresetdir}/50-speakerguardd-v2.preset
install -Dpm644 %{modulename}.pp.bz2 %{buildroot}%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2

%post
%systemd_post speakerguardd-v2.service speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service speakerguardd-v2-switchtest.service speakerguardd-v2-seat.path speakerguardd-v2-sleep.service
%systemd_user_post speakerguardd-v2-graph.service speakerguardd-v2-session.service
# Say at once which stack this Mac runs.
%{_libexecdir}/speakerguardd-v2/speakerguardd-gate explain --wait 0 || :
%preun
%systemd_preun speakerguardd-v2.service speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service speakerguardd-v2-switchtest.service speakerguardd-v2-seat.path speakerguardd-v2-sleep.service
%systemd_user_preun speakerguardd-v2-graph.service speakerguardd-v2-session.service
%postun
%systemd_postun_with_restart speakerguardd-v2.service
%systemd_postun speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service speakerguardd-v2-switchtest.service speakerguardd-v2-seat.path speakerguardd-v2-sleep.service

# The sleep unit is new in the 1.0.0~alpha.1-0.13 snapshot. %%systemd_post
# applies its preset on a first install only, so an upgrade from an older
# build applies it once here (later upgrades keep the admin's choice).
%triggerpostun -- speakerguardd-v2 < 1.0.0~alpha.1-0.13
if [ -x /usr/bin/systemctl ]; then
    systemctl --no-reload preset speakerguardd-v2-sleep.service >/dev/null 2>&1 || :
fi

%pre selinux
%selinux_relabel_pre -s %{selinuxtype}
%post selinux
%selinux_modules_install -s %{selinuxtype} %{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2
%postun selinux
if [ "$1" -eq 0 ]; then
    %selinux_modules_uninstall -s %{selinuxtype} %{modulename}
fi
%posttrans selinux
%selinux_relabel_post -s %{selinuxtype}

%files
%license LICENSE crates/aurora-speaker-tuning/LICENSE-aurora-audio-dsp
%doc README.md docs/DESIGN.md docs/NEW-PLATFORM.md README.packaging.md packaging/etc/speakerguardd.conf.example
%{_libexecdir}/speakerguardd-v2/
%{_bindir}/aurora-speaker-tuning
%{_libdir}/lv2/sgv2.lv2/
%{_datadir}/speakerguardd/
%{_unitdir}/speakerguardd-v2.service
%{_unitdir}/speakerguardd-v2-provision.service
%{_unitdir}/speakerguardd-v2-selfcheck.service
%{_unitdir}/speakerguardd-v2-switchtest.service
%{_unitdir}/speakerguardd-v2-seat.service
%{_unitdir}/speakerguardd-v2-seat.path
%{_unitdir}/speakerguardd-v2-sleep.service
%{_userunitdir}/speakerguardd-v2-session.service
%{_userunitdir}/speakerguardd-v2-graph.service
%dir %{_unitdir}/speakersafetyd.service.d
%{_unitdir}/speakersafetyd.service.d/60-speakerguardd-v2-gate.conf
%dir %{_unitdir}/speakerguardd.service.d
%{_unitdir}/speakerguardd.service.d/60-speakerguardd-v2-gate.conf
%{_presetdir}/50-speakerguardd-v2.preset
%{_userpresetdir}/50-speakerguardd-v2.preset

%files selinux
%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2
%ghost %verify(not md5 size mode mtime) %{_sharedstatedir}/selinux/%{selinuxtype}/active/modules/200/%{modulename}

%changelog
* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 1.0.0~alpha.1-0.34.20261109git416b1f513b9d
- Release candidate 8.1 (speakerguardd#131): the legacy units' gate runs
  privileged (speakersafetyd is a DynamicUser and could not read the upgrade's
  root-only setting, so a switched Mac started speakersafetyd, which held the
  sense PCM v2 needs: no speakers until reboot); a switched Mac gets the older
  daemons only on a stable refusal; --revert starts only the sense PCM's own
  unit; --check works on dual-interface kernels before the first switch.

* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 1.0.0~alpha.1-0.33.20261109gitf4bb2fdb4406
- Release candidate 8, back as an opt-in package: nothing in the default
  install pulls it, and on every kernel the gate keeps speakersafetyd in charge
  until aurora-speaker-upgrade has switched this Mac (it ships disabled).
- Dual-interface kernels (linux 98cb6a86): the gate reads "Speaker Protection
  Interface" (speakerguardd#117).
- speakerguardd-selfcheck verify: refuses tunings v2 renders unlike macOS
  (per-AID parity attestation, installed as parity.json) and boot-time graph
  xruns; the speaker sink wakes on period interrupts (#114).
- Parity: mstk algorithm-0 band-zero rate (#113), ToneMeister version-0
  peaks (#116), BuzzKill tracker (#120); per-macOS-release attestation
  blocks 25C56, 25G83 and 26A428 (#121).
- Dual-interface lease: the supervisor writes the interface at start, the
  switch test switches it, --revert hands the session back to the
  distribution's speaker graph (#123).
- Every graph sink is held at the PCM rate (a 44.1 kHz client during a
  re-grant no longer wedges the speakers) and the LV2 protect stage takes
  in-place ports (#121). The upgrade tool's boot unit records a refusal
  instead of retrying it every boot (#125).

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.31.20261108git5104994eda35
- Move to 5104994eda35 (Plan A release candidate 7): RC6b plus speakerguardd#101 (the
  protect input is an internal sink) and #106 (the speaker card's raw PCMs stay out of
  the desktop's device lists; pro-audio is off on the speaker card) and #107 (the amps
  and the sense form one internal link group, so wpctl lists them only under the
  protection graph). Desktops now list one built-in speaker output and one
  microphone, like macOS. No DSP, limit or volume-law change.
- Require aurora-audio >= 4.1-11: without its keep-profile rule a Mac with a headphone
  jack drops the built-in card to "off" when nothing is plugged in.

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.30.20261108gitbc52fc66f51f
- Move to bc52fc66f51f (Plan A release candidate 6b): RC6 plus speakerguardd#102, the
  self-check's silent switch test runs after login in the new
  speakerguardd-v2-switchtest.service. Before login only the binding and the cheap checks
  run, so the first boot after a kernel change no longer holds the login screen for the
  switch test (J616s 11.7 s -> 0.7 s). Every session's PipeWire and WirePlumber wait for
  the test (a few seconds), which now takes 7 coded captures instead of 13; the speakers
  come up when it passes.

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.29.20261108git20f6c3d8269d
- Move to 20f6c3d8269d (Plan A release candidate 6): RC5b plus the source-OS-selected
  multiband compressor band-zero law (the Neo's AID44 compressor now matches macOS) and
  Apple's speaker volume law: the voicing graph's volume dB follows the macOS HAL curve
  over the range the Mac's own tuning bundle states, so slider x% plays at the level macOS
  plays at x%. Slider 100% and the protection limits are unchanged.

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.28.20261108gita60c29697ec2
- Move to a60c29697ec2 (Plan A release candidate 5b): RC5 plus speakerguardd#100, the
  regrant click fix: the sgv2 LV2 plugin mutes the program while the speakers are withdrawn
  and ramps it in after a grant. No DSP or trim change. The packaged files are unchanged.

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.27.20261108git612408731383
- Move to 612408731383 (speakerguardd#99, Plan A release candidate 5): RC4b plus the ToneMeister
  Butterworth shelves in the unit's Float32 order (tmst row 13 exact) and the VirtualBass Float32
  crossover per object; trims re-derived: j413 woofers -0.043 dB, all others none. The packaged files are unchanged.

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.26.20261108git7234e7015477
- Move to 7234e7015477 (speakerguardd#98, Plan A release candidate 4b): RC4 with the trims re-derived
  against the macOS chain each Mac actually runs (the M1 Pro's speaker-ID strip, the M2's LowFlow
  property strip): j316s none, j413 woofers -0.041 dB, j616s and j700 none. The packaged files are unchanged.

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.25.20261108gita8bba4d0366e
- Move to a8bba4d0366e (speakerguardd#98, Plan A release candidate 4): ToneMeister peaks in the
  unit's Float32 order, the J700 first-grant heartbeat handoff, Norm algorithm 1 exact;
  trims j316s -0.097 dB, j413 woofers -0.884 dB, j616s and j700 none. The packaged files are unchanged.

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.24.20261108git44a479d80e0e
- Move to 44a479d80e0e (speakerguardd#96, Plan A release candidate 3): ToneMeister fused
  cascade, ControlFreak slow release, lsid build, automatic board qualification; trims unchanged
  (j316s -0.097 dB, j413 woofers -0.883 dB, j616s and j700 none). The packaged files are unchanged.
- The provisioning, seat and self-check units now run under the gate's prepare mode.

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.23.20261108git5828fe9db811
- Move to 5828fe9db811 (speakerguardd#95, Plan A release candidate 2): RC1 plus VirtualBass mono
  width, Norm algorithm 1 and ToneMeister type 17 (0 refusals, 0 stubs on every AID); trims unchanged
  (j316s -0.097 dB, j413 woofers -0.883 dB, j616s and j700 none). The packaged files are unchanged.

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.22.20261108git6506f3be5280
- Move to 6506f3be5280 (speakerguardd#94, Plan A release candidate 1): Comp, LowFlow, ControlFreak,
  Norm and VirtualBass laws at macOS parity; interim never-louder trims from the RC scans
  (j316s -0.097 dB, j413 woofers -0.883 dB, j616s and j700 none). The packaged files are unchanged.

* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.21.20261107git4d6273225e0d
- Move to 4d6273225e0d (speakerguardd#92). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, lsm2, atsp; spp3: J316s, J413, J616s; lsm2: J700; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.16.20261107git6858b0c8896e
- Move to 6858b0c8896e (speakerguardd#91). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, lsm2, atsp; spp3: J316s, J413, J616s; lsm2: J700; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.15.20261107git105f503083db
- Move to 105f503083db (speakerguardd#65, #83, #88, #89, #90). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, lsm2, atsp; spp3: J316s, J413, J616s; lsm2: J700; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.14.20261107gitf5b6933fd677
- Move to f5b6933fd677 (speakerguardd#87). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, atsp; spp3: J316s, J413, J616s; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.13.20261107git6d13c704202e
- Move to 6d13c704202e (speakerguardd#77, #79, #80, #84, #85). Installs speakerguardd-sleep.service (new upstream).
- Fleet gate data (gate.json, upstream's): units at parity: spp3, atsp; spp3: J316s, J413, J616s; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Fri Nov 06 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.12.20261106git403b362efd09
- Move to 403b362efd09 (no merged pull requests). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, atsp; spp3: J316s, J413, J616s; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Fri Nov 06 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.11.20261106gitdfa9cc97023e
- Move to dfa9cc97023e (no merged pull requests). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, atsp; every board.

* Fri Nov 06 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.10.20261106gitfc227db69716
- Move to fc227db69716 (speakerguardd#74). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, atsp; spp3: J316s, J413, J616s; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Fri Nov 06 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.9.20261106git3fb558de1589
- Move to 3fb558de1589 (speakerguardd#73). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, atsp; spp3: J316s, J413, J616s; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.8.20261105git3b79d29fc800
- Move to 3b79d29fc800 (speakerguardd#72). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, atsp; spp3: J316s, J413, J616s; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.7.20261105git4b58a18fa69c
- Move to 4b58a18fa69c (speakerguardd#63, #64, #66, #67, #69, #70, #71). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, atsp; spp3: J316s, J413, J616s; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.6.20261105git64b4e2e7e084
- Move to 64b4e2e7e084 (speakerguardd#60, #61). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, atsp; spp3: J316s, J413, J616s; atsp: J274, J293, J313, J375C, J375D, J473, J474s, J475C, J475D, J493.

* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.5.20261105git8d45c2a4d981
- Move to 8d45c2a4d981 (speakerguardd#58, #59). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3; spp3: J316s, J413, J616s.

* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.4.20261105giteffddd1826a2
- Move to effddd1826a2 (speakerguardd#55, #56). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, lsm2; spp3: J316s, J413, J616s; lsm2: J700.

* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.3.20261105git3d6dca349dfe
- Move to 3d6dca349dfe (speakerguardd#51, #52, #53, #54). The packaged files are unchanged.
- Fleet gate data (gate.json, upstream's): units at parity: spp3, lsm2; spp3: J316s, J413, J616s; lsm2: J700.

* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.2.20261105gita3c66c51e70c
- Move to a3c66c51e70c (speakerguardd#48, #45, #49 and #50). Every per-board value is
  derived from the Mac's device tree and tuning at run time; machines.json
  is gone and is no longer installed, and gate.json carries the qualified
  boards per protection unit (spp3: J316s, J413, J616s).
- The self-check unit no longer takes --machines; the v2 units read their
  configuration optionally, so a board or kernel the gate skips is skipped
  cleanly instead of failing at every boot and login.
- test_provision.py passes when %%check runs as root and without
  /usr/bin/env (speakerguardd#50).
- aurora-speaker-tuning reads the installer's macOS 27 manifest fields
  (speakerguardd#49).

* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.1.20261105gitebab1e0f7c4e
- Move to ebab1e0f7c4e (speakerguardd#44): automatic provisioning at boot
  (the tuning compiled and bound to board, kernel, bundle and macOS build;
  the seat user resolved by name; the configuration and the speaker graph),
  and the fleet gate, upstream's program with upstream's data.
- Install everywhere, gate by board: aurora-platform and aurora-audio
  require this package beside speakersafetyd and speakerguardd 0.1, its
  units are enabled by preset, and the gate (ExecCondition of both stacks)
  starts v2 on a gated board whose kernel has the v2 interface and the
  older daemons everywhere else. The replace-legacy opt-in is gone; rollback
  is booting a kernel without the v2 interface.
- Run upstream's test_provision.py in %%check.

* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.1.20261105git3c18a3527055
- Move to the integrated v2 tree (ebab1e0f7c4e: speakerguardd#41, #42 and
  #43). Under #42 a derivable board never falls back to a hand map. Under
  #43 the closed loop relaxes only on a board proven for it (the J616s
  family) and runs capped elsewhere.: the
  engine with spp3 at parity, the supervisor, the session helper and the
  first-boot wiring self-check.
- Ship speakerguardd-v2-selfcheck.service as a hard prerequisite of the
  supervisor (Requires= and After=), and the session helper as a user unit.
- Build upstream's SELinux policy module (packaging/selinux), with this
  package's file contexts, now also for /var/lib/speakerguardd.
- The opt-in's units start only on a board that qualified on 1.0 (J616s, J316s, J413);
  elsewhere the journal says why and the kernel's safe level holds.

* Wed Nov 04 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.1.20261104gitf06b9697e648
- Initial preview package of speakerguardd 1.0 (the v2 branch at
  f06b9697e648): the supervisor, the sgv2 LV2 bundle and the
  aurora-speaker-tuning reader, with its own SELinux policy module.
- It installs beside speakerguardd 0.1 and speakersafetyd and enables
  nothing; speakerguardd-v2-replace-legacy is the opt-in switch, with no
  Obsoletes or Provides, so dnf never picks it on its own.
