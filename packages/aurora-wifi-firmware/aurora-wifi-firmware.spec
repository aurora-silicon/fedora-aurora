%global commit 79a75495b160fcd92b76b0374f0acb4ca30f3a7b
%global shortcommit %{lua:print(string.sub(rpm.expand("%{commit}"), 1, 12))}
%global snapdate 20261113

Name: aurora-wifi-firmware
Version: 0.1
Release: 1.%{snapdate}git%{shortcommit}%{?dist}
Summary: Keep the Wi-Fi firmware on the installed macOS's
License: MIT
URL: https://github.com/aurora-silicon/aurora-installer/tree/main/tools/wifi-firmware
Source0: aurora-wifi-firmware-%{commit}.tar.gz
Source1: 80-aurora-wifi-firmware.preset
BuildArch: noarch
BuildRequires: make systemd-rpm-macros python3
Requires: python3 lzfse-libs util-linux systemd
%{?systemd_requires}

%description
macOS runs the Wi-Fi firmware its own system volume ships, so a macOS update
brings new Wi-Fi firmware. aurora-wifi-firmware reads the installed macOS's
Wi-Fi firmware from Linux (read only, from the System volume, which is not
encrypted), converts it with the installer's converter and, when it differs
from the ESP's, puts it on the ESP for the next boot with a backup. The boot
after a change checks that brcmfmac came up with it and puts the previous
files back if not. The service runs at every boot. Apple's firmware stays on
the Mac; this package carries none.

%prep
%autosetup -n aurora-installer-%{commit}

%build

%check
python3 -I -m unittest discover -s tests -p 'test_wifi_firmware_*.py'

%install
%make_install -C tools/wifi-firmware PREFIX=%{_prefix} UNITDIR=%{_unitdir} PYTHON=%{python3}
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
* Fri Nov 13 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1-1.20261113git79a75495b160
- First package: aurora-installer tools/wifi-firmware (aurora-installer#131).
