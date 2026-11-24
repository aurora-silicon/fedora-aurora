%global commit 873ce2e1f48c66bf2e6b66bdedbfb32559c865b8
%global shortcommit %{lua:print(string.sub(rpm.expand("%{commit}"), 1, 12))}
%global snapdate 20261124

Name: aurora-wifi-firmware
Version: 0.3
Release: 1.%{snapdate}git%{shortcommit}%{?dist}
Summary: Keep the Wi-Fi and Bluetooth firmware on the stub firmware's restore image
License: MIT
URL: https://github.com/aurora-silicon/aurora-installer/tree/main/tools/wifi-firmware
Source0: aurora-wifi-firmware-%{commit}.tar.gz
Source1: 80-aurora-wifi-firmware.preset
BuildArch: noarch
BuildRequires: make systemd-rpm-macros python3
Requires: python3 python3-cryptography lzfse-libs util-linux systemd
%{?systemd_requires}

%description
Radio firmware is per-model, per-version data, so it comes from one source:
Apple's restore image (IPSW) of the macOS version this Mac's stub firmware
runs, for its board, read by HTTP ranges and authenticated (AEA) or checked
against its BuildManifest. aurora-wifi-firmware converts that image's Wi-Fi
and Bluetooth firmware with the installer's converters and, when it differs
from the ESP's, puts it on the ESP for the next boot with a backup. The boot
after a change checks that the drivers came up with it and puts the previous
files back if not. A boot with nothing changed needs no network. Apple's
firmware stays on the Mac; this package carries none.

%prep
%autosetup -n aurora-installer-%{commit}

%build

%check
python3 -I -m unittest discover -s tests -p 'test_wifi_firmware_*.py'

%install
%make_install -C tools/wifi-firmware PREFIX=%{_prefix} UNITDIR=%{_unitdir} PYTHON=%{python3}
# The refresh tool uses the same ESP staging directory.
sed -i 's|^exec |exec %{_bindir}/flock -x /run/lock/aurora-firmware.lock |' \
    %{buildroot}%{_bindir}/aurora-wifi-firmware
install -Dm644 %{SOURCE1} %{buildroot}%{_presetdir}/80-aurora-wifi-firmware.preset

%post
%systemd_post aurora-wifi-firmware.service

%preun
%systemd_preun aurora-wifi-firmware.service

%postun
%systemd_postun aurora-wifi-firmware.service

%files
%license LICENSE
%doc tools/wifi-firmware/README.md
%{_bindir}/aurora-wifi-firmware
%{_prefix}/lib/aurora-wifi-firmware/
%{_unitdir}/aurora-wifi-firmware.service
%{_presetdir}/80-aurora-wifi-firmware.preset

%changelog
* Tue Nov 24 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.3-1.20261124git873ce2e1f48c
- Radio firmware comes only from Apple's restore image of the stub
  firmware's macOS version for this board (aurora-installer#226), never
  from an installed macOS. A boot with nothing changed needs no network;
  the unit runs after network-online.target. Needs python3-cryptography.

* Tue Nov 24 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.2-2
- Serialize the radio and firmware refresh tools.

* Fri Nov 13 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.2-1.20261113gitafdd3215189c
- Bluetooth (Broadcom) and the MacBook Neo's MT7932 Wi-Fi and Bluetooth firmware follow the installed macOS too (aurora-installer#134).

* Fri Nov 13 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-1.20261113git79a75495b160
- First package: aurora-installer tools/wifi-firmware (aurora-installer#131).
