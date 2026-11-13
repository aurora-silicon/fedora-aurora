# speakersafetyd 2.0.1, the version Fedora ships, rebuilt with two downstream
# fixes: a sense period read after a startup probe closed the speakers no
# longer panics the daemon (0002), and a machine's own configuration
# (apple/j575c.conf) is tried before its family's (apple/j575.conf) (0003).
# 0001 is Fedora's own backport, kept so this build carries everything
# Fedora's does. Nothing else of speakersafetyd is changed.
Name: speakersafetyd
Version: 2.0.1
Release: 1%{?dist}.aurora2
Summary: Speaker protection daemon for embedded Linux systems
License: MIT
URL: https://crates.io/crates/speakersafetyd
Source0: speakersafetyd-%{version}.crate
Patch0: 0001-j504-Write-the-full-speaker-names-in-conf.patch
Patch1: 0002-skip-a-sense-period-read-after-a-probe-closed-the-speakers.patch
Patch2: 0003-try-the-machine-s-own-config-before-its-family-s.patch
ExclusiveArch: aarch64
BuildRequires: rust cargo alsa-lib-devel systemd-rpm-macros
Requires: systemd-udev
%{?systemd_requires}

%description
Speaker protection daemon for embedded Linux systems: it models each
speaker's voice coil and magnet temperature from the amplifiers' voltage
and current sense and lowers the speaker gain before a limit is reached.

%prep
%autosetup -n speakersafetyd-%{version} -p1

%build
cargo build --locked --release

%check
cargo test --locked --release

%install
install -p -m 0755 -D target/release/speakersafetyd %{buildroot}%{_bindir}/speakersafetyd
install -p -m 0644 -D speakersafetyd.service %{buildroot}%{_unitdir}/speakersafetyd.service
install -p -m 0644 -D 95-speakersafetyd.rules %{buildroot}%{_udevrulesdir}/95-speakersafetyd.rules
install -d -m 0755 %{buildroot}%{_datadir}/speakersafetyd/apple
install -p -m 0644 -t %{buildroot}%{_datadir}/speakersafetyd/apple conf/apple/*
install -d -m 0755 %{buildroot}%{_sharedstatedir}/speakersafetyd/blackbox

%post
%systemd_post speakersafetyd.service

%preun
%systemd_preun speakersafetyd.service

%postun
%systemd_postun_with_restart speakersafetyd.service

%files
%license LICENSE
%doc README.md
%{_bindir}/speakersafetyd
%{_datadir}/speakersafetyd/
%{_unitdir}/speakersafetyd.service
%{_sharedstatedir}/speakersafetyd/
%{_udevrulesdir}/95-speakersafetyd.rules

%changelog
* Thu Nov 13 2026 Ryan Murray <ryan@aurorasilicon.org> - 2.0.1-1.aurora2
- Try the machine's own configuration (apple/j575c.conf) before its family's
  (apple/j575.conf), so a variant whose speaker sense differs from its family
  (the Mac Studio M4 Max J575c, whose AOP speaker stream carries twelve sense
  channels where j575.conf describes two) gets its own profile instead of
  panicking the daemon and leaving the speaker at the kernel's floor (0003).
  Port of alarm-aurora#267 by Roberto Dantas.

* Mon Nov 09 2026 Ryan Murray <ryan@aurorasilicon.org> - 2.0.1-1.aurora1
- Rebuild Fedora's speakersafetyd 2.0.1 with one downstream fix: a sense
  period read after a startup probe closed the speakers is skipped instead
  of panicking the daemon (every boot and PipeWire restart on an M2 Air).
  Any other invalid rate still fails safe.
