%global commit f06b9697e64843807cec9c09af9af13756c6ac3c
%global shortcommit %{lua:print(string.sub(rpm.expand("%{commit}"), 1, 12))}
%global snapdate 20261104
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
Source1: speakerguardd.te
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
%{?systemd_requires}

%description
speakerguardd 1.0 is a new speaker protection stack that works the way
macOS's does: the protection unit runs inside the PipeWire speaker graph as
an LV2 plugin, with the amplifier's voltage and current sense as its second
input where the Mac has it, driven by that Mac's own tuning bundle.

This preview installs beside the 0.1 speakerguardd and speakersafetyd and
changes nothing on its own: the speakerguardd-v2 service is not enabled, and
no graph loads the plugin. Machines move to it only after they qualify,
through the speakerguardd-v2-replace-legacy package.

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
cp -p %{SOURCE1} %{SOURCE2} .
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
# The upstream unit, under its own name so it installs beside the 0.1 unit.
install -Dm644 packaging/systemd/speakerguardd.service %{buildroot}%{_unitdir}/speakerguardd-v2.service
sed -i 's@^ExecStart=/usr/bin/speakerguardd$@ExecStart=%{_libexecdir}/speakerguardd-v2/speakerguardd@' \
    %{buildroot}%{_unitdir}/speakerguardd-v2.service
grep -qx 'ExecStart=%{_libexecdir}/speakerguardd-v2/speakerguardd' %{buildroot}%{_unitdir}/speakerguardd-v2.service
if grep -Eq '^(OnFailure|OnSuccess)=|speakersafetyd' %{buildroot}%{_unitdir}/speakerguardd-v2.service; then
    echo 'The speakerguardd 1.0 unit must not chain to another daemon' >&2; exit 1
fi
install -Dpm644 %{SOURCE3} %{buildroot}%{_presetdir}/50-speakerguardd-v2.preset
install -Dpm644 %{modulename}.pp.bz2 %{buildroot}%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2

%post
%systemd_post speakerguardd-v2.service
%preun
%systemd_preun speakerguardd-v2.service
%postun
%systemd_postun_with_restart speakerguardd-v2.service

# The preset in this package enables the unit when it is installed.
%post replace-legacy
%systemd_post speakerguardd-v2.service
%preun replace-legacy
if [ "$1" -eq 0 ] && [ -x /usr/bin/systemctl ]; then
    systemctl --no-reload disable speakerguardd-v2.service >/dev/null 2>&1 || :
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
%doc README.md docs/DESIGN.md README.packaging.md
%{_libexecdir}/speakerguardd-v2/
%{_bindir}/aurora-speaker-tuning
%{_libdir}/lv2/sgv2.lv2/
%{_unitdir}/speakerguardd-v2.service

%files selinux
%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2
%ghost %verify(not md5 size mode mtime) %{_sharedstatedir}/selinux/%{selinuxtype}/active/modules/200/%{modulename}

%files replace-legacy
%{_presetdir}/50-speakerguardd-v2.preset

%changelog
* Wed Nov 04 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~alpha.1-0.1.20261104gitf06b9697e648
- Initial preview package of speakerguardd 1.0 (the v2 branch at
  f06b9697e648): the supervisor, the sgv2 LV2 bundle and the
  aurora-speaker-tuning reader, with its own SELinux policy module.
- It installs beside speakerguardd 0.1 and speakersafetyd and enables
  nothing; speakerguardd-v2-replace-legacy is the opt-in switch, with no
  Obsoletes or Provides, so dnf never picks it on its own.
