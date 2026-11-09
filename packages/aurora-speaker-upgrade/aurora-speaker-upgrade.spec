%global commit f4bb2fdb44066fc081669b4b43c9db4d766a45e1
%global shortcommit %{lua:print(string.sub(rpm.expand("%{commit}"), 1, 12))}
%global snapdate 20261109

Name: aurora-speaker-upgrade
Version: 0.1
Release: 0.3.%{snapdate}git%{shortcommit}%{?dist}
Summary: Move the speakers to speakerguardd v2 with this Mac's own tuning (preview)
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
* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.3
- Enable aurora-speaker-upgrade.service by preset (Ryan + DJ go): the next
  boot moves the speakers to speakerguardd v2 when this Mac's own tuning
  passes the silent self-check; a refused Mac keeps speakersafetyd.

* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-0.2.20261109gitf4bb2fdb4406
- speakerguardd v2 release candidate 8: the dual-interface kernel's lease
  (hardware record before verify; --revert hands the session back to the
  distribution's speaker graph), and the boot unit records a refusal instead
  of retrying it at every boot (exit 1 is an outcome). Still ships disabled.

* Mon Nov 09 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1-0.1
- First preview: routes 0-3, root-only store, v2 self-check gate,
  interface switch, --revert. Ships disabled.
