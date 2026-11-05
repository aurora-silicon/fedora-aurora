%global commit 3c18a3527055145bc8b98e82c00b5deb4ca9a42f
%global shortcommit %{lua:print(string.sub(rpm.expand("%{commit}"), 1, 12))}
%global snapdate 20261105
%global selinuxtype targeted
%global modulename speakerguardd
# The crates this package ships; the rig and benchmark crates stay out.
%global cargo_pkgs -p sgv2-core -p sgv2-lv2 -p sgv2-supervisor -p aurora-speaker-tuning

Name: speakerguardd-v2
Version: 1.0.0~alpha.1
Release: 0.1.%{snapdate}git%{shortcommit}%{?dist}
Summary: In-graph speaker protection for Apple Silicon Macs (speakerguardd 1.0, preview)
# aurora-speaker-tuning is based on aurora-audio-dsp by saku, also MIT.
License: MIT
URL: https://github.com/aurora-silicon/speakerguardd
Source0: speakerguardd-v2-%{commit}.tar.gz
Source1: speakerguardd-v2-gate
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
# The self-check and the session helper: Python, the ALSA tools for the
# silent switch test, and pw-link/pw-dump for the speaker graph.
Requires: python3 alsa-utils pipewire-utils
%{?systemd_requires}

%description
speakerguardd 1.0 is a new speaker protection stack that works the way
macOS's does: the protection unit runs inside the PipeWire speaker graph as
an LV2 plugin, with the amplifier's voltage and current sense as its second
input where the Mac has it, driven by that Mac's own tuning bundle.

It ships the supervisor, the first-boot wiring self-check (a hard
prerequisite of the supervisor), the session helper, the sgv2 LV2 bundle and
the aurora-speaker-tuning reader. It installs beside the 0.1 speakerguardd
and speakersafetyd and changes nothing on its own: no unit is enabled, and no
graph loads the plugin. Machines move to it only after they qualify, through
the speakerguardd-v2-replace-legacy package, whose units start only on a
qualified board.

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
and labels its program and its runtime directory, where it publishes the
plugin's parameters and engine page.

%package replace-legacy
Summary: Opt in: make speakerguardd 1.0 the speaker protection, replacing 0.1 and speakersafetyd
BuildArch: noarch
Requires: %{name} = %{version}-%{release}
# Installing this package is the switch. It takes the place of both older
# daemons, which must not hold the speaker interlock beside it.
# - No Obsoletes: one in the repository would make every upgrade swap a
#   machine over without asking, and a machine moves only once it qualifies.
# - No Provides of speakerguardd or speakersafetyd either: dnf would then
#   choose this package to satisfy a plain Requires on them, so a fresh
#   install would get it unasked. aurora-audio and aurora-platform instead
#   require (speakersafetyd or speakerguardd-v2-replace-legacy) and recommend
#   the real daemons, which dnf then prefers.
Conflicts: speakerguardd < 1.0.0~
Conflicts: speakersafetyd
%{?systemd_requires}

%description replace-legacy
Installing this package makes speakerguardd 1.0 the machine's speaker
protection: it removes the 0.1 speakerguardd and speakersafetyd (install it
with dnf --allowerasing) and enables speakerguardd-v2.service. Install
it only on a machine that passed the 1.0 qualification; until then the
machine keeps the protection it runs today. See
%{_docdir}/%{name}/README.md.

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
# The upstream units, under their own names so they install beside the 0.1
# unit, with the programs where this package installs them.
lx=%{_libexecdir}/speakerguardd-v2
install -Dm755 packaging/session/speakerguardd-selfcheck %{buildroot}$lx/speakerguardd-selfcheck
install -Dm755 packaging/session/speakerguardd-session %{buildroot}$lx/speakerguardd-session
install -Dm644 packaging/session/wiring.py %{buildroot}$lx/wiring.py
install -Dm644 packaging/session/machines.json %{buildroot}%{_datadir}/speakerguardd/machines.json
install -Dm755 %{SOURCE1} %{buildroot}$lx/speakerguardd-v2-gate
# The per-machine graphs, as data: the opt-in's provisioning activates one.
for f in packaging/pipewire/sgv2-*.conf; do
    install -Dpm644 $f %{buildroot}%{_datadir}/speakerguardd/pipewire/$(basename $f)
done
for f in packaging/wireplumber/60-sgv2-*.conf; do
    install -Dpm644 $f %{buildroot}%{_datadir}/speakerguardd/wireplumber/$(basename $f)
done
sed -e "s@^ExecStart=/usr/bin/speakerguardd @ExecStart=$lx/speakerguardd @" \
    -e 's@speakerguardd-selfcheck\.service@speakerguardd-v2-selfcheck.service@g' \
    packaging/systemd/speakerguardd.service > speakerguardd-v2.service
sed -e "s@/usr/libexec/speakerguardd/speakerguardd-selfcheck@$lx/speakerguardd-selfcheck@" \
    -e 's@^\(Before\|RequiredBy\)=speakerguardd\.service$@\1=speakerguardd-v2.service@' \
    packaging/systemd/speakerguardd-selfcheck.service > speakerguardd-v2-selfcheck.service
sed -e "s@^ExecStart=/usr/libexec/speakerguardd-session @ExecStart=$lx/speakerguardd-session @" \
    packaging/systemd/speakerguardd-session.service > speakerguardd-v2-session.service
# Each rewrite must have taken, and no unit may chain to another daemon.
grep -qx "ExecStart=$lx/speakerguardd \$SGV2_ARGS" speakerguardd-v2.service
grep -qx 'Requires=speakerguardd-v2-selfcheck.service' speakerguardd-v2.service
grep -q '^After=.*speakerguardd-v2-selfcheck.service' speakerguardd-v2.service
grep -q "^ExecStart=$lx/speakerguardd-selfcheck run " speakerguardd-v2-selfcheck.service
grep -qx 'Before=speakerguardd-v2.service' speakerguardd-v2-selfcheck.service
grep -qx 'RequiredBy=speakerguardd-v2.service' speakerguardd-v2-selfcheck.service
grep -q "^ExecStart=$lx/speakerguardd-session " speakerguardd-v2-session.service
if grep -Eq '^(OnFailure|OnSuccess)=|speakersafetyd|=speakerguardd\.service' speakerguardd-v2*.service; then
    echo 'A speakerguardd 1.0 unit chains to or names another daemon' >&2; exit 1
fi
install -Dm644 speakerguardd-v2.service %{buildroot}%{_unitdir}/speakerguardd-v2.service
install -Dm644 speakerguardd-v2-selfcheck.service %{buildroot}%{_unitdir}/speakerguardd-v2-selfcheck.service
# The session helper follows the user's PipeWire.
install -Dm644 speakerguardd-v2-session.service %{buildroot}%{_userunitdir}/speakerguardd-v2-session.service
# The board gate, in the opt-in only: on a board that has not qualified the
# units do not start, and the journal says why.
for u in speakerguardd-v2 speakerguardd-v2-selfcheck; do
    install -d %{buildroot}%{_unitdir}/$u.service.d
    printf '[Service]\nExecCondition=%s/speakerguardd-v2-gate\n' "$lx" > %{buildroot}%{_unitdir}/$u.service.d/50-qualified-board.conf
done
install -d %{buildroot}%{_userunitdir}/speakerguardd-v2-session.service.d
printf '[Service]\nExecCondition=%s/speakerguardd-v2-gate\n' "$lx" > %{buildroot}%{_userunitdir}/speakerguardd-v2-session.service.d/50-qualified-board.conf
install -Dpm644 %{SOURCE3} %{buildroot}%{_presetdir}/50-speakerguardd-v2.preset
install -d %{buildroot}%{_userpresetdir}
echo 'enable speakerguardd-v2-session.service' > %{buildroot}%{_userpresetdir}/50-speakerguardd-v2.preset
install -Dpm644 %{modulename}.pp.bz2 %{buildroot}%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2

%post
%systemd_post speakerguardd-v2.service speakerguardd-v2-selfcheck.service
%systemd_user_post speakerguardd-v2-session.service
%preun
%systemd_preun speakerguardd-v2.service speakerguardd-v2-selfcheck.service
%systemd_user_preun speakerguardd-v2-session.service
%postun
%systemd_postun_with_restart speakerguardd-v2.service
%systemd_postun speakerguardd-v2-selfcheck.service

# The preset in this package enables the unit when it is installed.
%post replace-legacy
%systemd_post speakerguardd-v2.service speakerguardd-v2-selfcheck.service
%systemd_user_post speakerguardd-v2-session.service
# Say at once when this board will not start speakerguardd 1.0.
%{_libexecdir}/speakerguardd-v2/speakerguardd-v2-gate || :
%preun replace-legacy
if [ "$1" -eq 0 ] && [ -x /usr/bin/systemctl ]; then
    systemctl --no-reload disable speakerguardd-v2.service speakerguardd-v2-selfcheck.service >/dev/null 2>&1 || :
    systemctl --no-reload --global disable speakerguardd-v2-session.service >/dev/null 2>&1 || :
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
%{_unitdir}/speakerguardd-v2-selfcheck.service
%{_userunitdir}/speakerguardd-v2-session.service

%files selinux
%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2
%ghost %verify(not md5 size mode mtime) %{_sharedstatedir}/selinux/%{selinuxtype}/active/modules/200/%{modulename}

%files replace-legacy
%{_presetdir}/50-speakerguardd-v2.preset
%{_userpresetdir}/50-speakerguardd-v2.preset
%{_unitdir}/speakerguardd-v2.service.d/50-qualified-board.conf
%{_unitdir}/speakerguardd-v2-selfcheck.service.d/50-qualified-board.conf
%{_userunitdir}/speakerguardd-v2-session.service.d/50-qualified-board.conf

%changelog
* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.1.20261105git3c18a3527055
- Move to the integrated v2 tree (3c18a3527055: speakerguardd#41, #42 and
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
