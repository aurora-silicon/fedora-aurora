%global commit 873ce2e1f48c66bf2e6b66bdedbfb32559c865b8
%global refreshdir %{_prefix}/lib/aurora-firmware-refresh

Name: aurora-firmware-refresh
Version: 20261124
Release: 2%{?dist}
Summary: Refresh the firmware supplied by the Aurora installer
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
Source0: aurora-firmware-refresh-%{commit}.tar.gz
Source1: refresh.py
Source2: test_refresh.py
BuildArch: noarch
BuildRequires: python3
Requires: python3 python3-cryptography lzfse-libs util-linux
Requires: aurora-wifi-firmware >= 0.3
Provides: asahi-fwupdate = %{version}-%{release}
Obsoletes: asahi-fwupdate < %{version}
Provides: python3-asahi_firmware = 0.9.2
Obsoletes: python3-asahi_firmware < 0.9.3

%description
Use the Aurora installer's converter to add missing vendor firmware from
this Mac's existing firmware archive. Keep the files already in use,
including radio firmware and speaker tuning. Installing the RPM never
rewrites the ESP. The package contains tools and no firmware.

%prep
%setup -q -n aurora-installer-%{commit}

%build

%install
install -Dm644 %{SOURCE1} %{buildroot}%{refreshdir}/refresh.py
for file in asahi_firmware/*.py asahi_firmware/restore-images.json tools/wifi-firmware/aurora_wifi_firmware.py; do
    install -Dm644 "$file" "%{buildroot}%{refreshdir}/${file#tools/wifi-firmware/}"
done
install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/aurora-firmware-refresh <<'SCRIPT'
#!/bin/sh
exec %{python3} -I -B %{refreshdir}/refresh.py "$@"
SCRIPT
chmod 0755 %{buildroot}%{_bindir}/aurora-firmware-refresh

%check
PYTHONPATH=%{buildroot}%{refreshdir} %{python3} -B %{SOURCE2}

%files
%license LICENSE
%{_bindir}/aurora-firmware-refresh
%{refreshdir}/

%changelog
* Tue Nov 24 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 20261124-2
- Rebuilt from aurora-installer 873ce2e1: apfs_ro moved into asahi_firmware with
  the restore image reader (aurora-installer#226).

* Tue Nov 24 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261124-1
- Replace the Fedora firmware extractor and its RPM transaction trigger.
