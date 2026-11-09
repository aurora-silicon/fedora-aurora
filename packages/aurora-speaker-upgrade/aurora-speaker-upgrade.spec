%global commit 3fbe180b5c634350c1ece5e0da650109abf40edd
%global shortcommit %{lua:print(string.sub(rpm.expand("%{commit}"), 1, 12))}
%global snapdate 20261109

Name: aurora-speaker-upgrade
Version: 0.1
Release: 0.1.%{snapdate}git%{shortcommit}%{?dist}
Summary: Move the speakers to speakerguardd v2 with this Mac's own tuning (preview)
# The vendored installer collector (asahi_firmware) and the AEA range port
# (from macos-firmware-extract) are MIT as well.
License: MIT
URL: https://github.com/aurora-silicon/speakerguardd/tree/v2/packaging/upgrade
Source0: aurora-speaker-upgrade-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: make systemd-rpm-macros python3 python3-cryptography
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
%dir %{_unitdir}/speakerguardd-v2.service.d
%{_unitdir}/speakerguardd-v2.service.d/50-aurora-speaker-upgrade.conf

%changelog
* Mon Nov 09 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1-0.1
- First preview: routes 0-3, root-only store, v2 self-check gate,
  interface switch, --revert. Ships disabled.
