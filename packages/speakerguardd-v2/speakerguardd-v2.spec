%global commit 3d6dca349dfe4981f81da70865387ec5783ca152
%global shortcommit %{lua:print(string.sub(rpm.expand("%{commit}"), 1, 12))}
%global snapdate 20261105
%global selinuxtype targeted
%global modulename speakerguardd
# The crates this package ships; the rig and benchmark crates stay out.
%global cargo_pkgs -p sgv2-core -p sgv2-lv2 -p sgv2-supervisor -p aurora-speaker-tuning

Name: speakerguardd-v2
Version: 1.0.0~alpha.1
Release: 0.3.%{snapdate}git%{shortcommit}%{?dist}
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
for u in speakerguardd.service speakerguardd-provision.service speakerguardd-selfcheck.service \
         speakerguardd-seat.service speakerguardd-seat.path speakerguardd-session.service speakerguardd-graph.service; do
    rename_units packaging/systemd/$u > ${u/speakerguardd/speakerguardd-v2}
done
# Each rewrite must have taken, and no unit may chain to another daemon.
grep -qx "ExecStart=$lx/speakerguardd \$SGV2_ARGS" speakerguardd-v2.service
grep -qx 'Requires=speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service' speakerguardd-v2.service
grep -q '^After=.*speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service' speakerguardd-v2.service
grep -qx 'Requires=speakerguardd-v2-provision.service' speakerguardd-v2-selfcheck.service
grep -qx 'Before=speakerguardd-v2-selfcheck.service speakerguardd-v2.service' speakerguardd-v2-provision.service
grep -qx "ExecStart=$lx/speakerguardd-provision run" speakerguardd-v2-provision.service
grep -qx "ExecStartPost=$lx/speakerguardd-provision activate --graph-unit speakerguardd-v2-graph.service" speakerguardd-v2-selfcheck.service
grep -qx "ExecStart=$lx/speakerguardd-provision seat --unit speakerguardd-v2.service" speakerguardd-v2-seat.service
grep -qx 'Unit=speakerguardd-v2-seat.service' speakerguardd-v2-seat.path
grep -qx "ExecCondition=$lx/speakerguardd-provision is-seat" speakerguardd-v2-session.service
grep -q "^ExecStart=$lx/speakerguardd-session " speakerguardd-v2-session.service
for u in speakerguardd-v2.service speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service speakerguardd-v2-seat.service; do
    grep -qx "ExecCondition=$lx/speakerguardd-gate v2" $u
done
if grep -Eq '^(OnFailure|OnSuccess)=|speakersafetyd|=speakerguardd\.service|/usr/libexec/speakerguardd/' speakerguardd-v2*.service speakerguardd-v2*.path; then
    echo 'A speakerguardd 1.0 unit chains to or names another daemon' >&2; exit 1
fi
for u in speakerguardd-v2.service speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service \
         speakerguardd-v2-seat.service speakerguardd-v2-seat.path; do
    install -Dm644 $u %{buildroot}%{_unitdir}/$u
done
for u in speakerguardd-v2-session.service speakerguardd-v2-graph.service; do
    install -Dm644 $u %{buildroot}%{_userunitdir}/$u
done
# The older daemons start only where v2 does not run and the kernel has no
# v2 interface: exactly one stack holds the speakers on each boot.
sed -e "s@/usr/libexec/speakerguardd/@$lx/@g" packaging/systemd/legacy-gate.conf > legacy-gate.conf
grep -qx "ExecCondition=$lx/speakerguardd-gate legacy" legacy-gate.conf
for u in speakersafetyd speakerguardd; do
    install -Dm644 legacy-gate.conf %{buildroot}%{_unitdir}/$u.service.d/60-speakerguardd-v2-gate.conf
done
install -Dpm644 %{SOURCE3} %{buildroot}%{_presetdir}/50-speakerguardd-v2.preset
install -d %{buildroot}%{_userpresetdir}
printf 'enable speakerguardd-v2-graph.service\nenable speakerguardd-v2-session.service\n' > %{buildroot}%{_userpresetdir}/50-speakerguardd-v2.preset
install -Dpm644 %{modulename}.pp.bz2 %{buildroot}%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2

%post
%systemd_post speakerguardd-v2.service speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service speakerguardd-v2-seat.path
%systemd_user_post speakerguardd-v2-graph.service speakerguardd-v2-session.service
# Say at once which stack this Mac runs.
%{_libexecdir}/speakerguardd-v2/speakerguardd-gate explain --wait 0 || :
%preun
%systemd_preun speakerguardd-v2.service speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service speakerguardd-v2-seat.path
%systemd_user_preun speakerguardd-v2-graph.service speakerguardd-v2-session.service
%postun
%systemd_postun_with_restart speakerguardd-v2.service
%systemd_postun speakerguardd-v2-provision.service speakerguardd-v2-selfcheck.service speakerguardd-v2-seat.path

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
%{_unitdir}/speakerguardd-v2-seat.service
%{_unitdir}/speakerguardd-v2-seat.path
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
