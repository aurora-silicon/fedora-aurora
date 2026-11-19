%global commit 9b47a17827854588d458b1dcc8018c66f5c3237f
Name: aurora-bless
Version: 0.4.4
Release: 4%{?dist}
Summary: Apple Silicon startup volume selector with Neo NVRAM support
License: MIT
URL: https://github.com/aurora-silicon/aurora-bless
Source0: aurora-bless-%{commit}.tar.gz
ExclusiveArch: aarch64
Provides: asahi-bless
Conflicts: asahi-bless
BuildRequires: rust cargo make systemd-rpm-macros pkgconfig(dbus-1)

%description
Apple Silicon startup volume selector with Neo NVRAM support. Built from the recorded Aurora source revision.

%package -n aurora-panel-nits
Summary: Built-in panel brightness shared with the boot loader through NVRAM

%description -n aurora-panel-nits
The boot loader lights the built-in panel at the NVRAM backlight-nits level,
which macOS keeps at the user's level. This service starts the panel at that
level when Linux takes over, instead of a level of its own, and stores the
level the user picks back in NVRAM (after 5 s without a change, at most once
a minute, and at shutdown), so the boot loader, Linux and macOS share one
brightness.

%package -n aurora-nvram
Summary: Read and write Apple Silicon NVRAM variables
Provides: asahi-nvram = %{version}-%{release}
Obsoletes: asahi-nvram < %{version}-%{release}
Conflicts: asahi-nvram

%description -n aurora-nvram
Reads, writes and deletes NVRAM variables on Apple Silicon Macs, including
the NVRAM v3 stores of current Macs. Reads open the device read-only; writes
take the NVRAM lock and the boot NOR write window. Replaces asahi-nvram, which
is kept as a symlink.

%package -n aurora-btsync
Summary: Use the Bluetooth pairings made in macOS on Linux
Requires: bluez
Provides: asahi-btsync = %{version}-%{release}
Obsoletes: asahi-btsync < %{version}-%{release}
Conflicts: asahi-btsync

%description -n aurora-btsync
Copies the Bluetooth pairings macOS keeps in NVRAM into BlueZ's storage when
the NVRAM device appears, and refreshes the keys of devices macOS paired
again. Pairings made only on Linux are left alone. Replaces asahi-btsync; the
asahi-btsync command and asahi-btsync.service stay available as aliases.

%prep
%autosetup -n aurora-bless-9b47a17827854588d458b1dcc8018c66f5c3237f

%build
cargo build --locked --release -p asahi-bless -p aurora-nvram -p aurora-btsync -p aurora-panel-nits

%check
cargo test --locked -p asahi-bless -p apple-nvram -p aurora-nvram -p aurora-btsync -p aurora-panel-nits

%install
install -Dm755 target/release/asahi-bless %{buildroot}%{_bindir}/aurora-bless
ln -s aurora-bless %{buildroot}%{_bindir}/asahi-bless
install -Dm755 target/release/aurora-nvram %{buildroot}%{_bindir}/aurora-nvram
ln -s aurora-nvram %{buildroot}%{_bindir}/asahi-nvram
install -Dm755 target/release/aurora-btsync %{buildroot}%{_bindir}/aurora-btsync
ln -s aurora-btsync %{buildroot}%{_bindir}/asahi-btsync
install -Dm644 aurora-btsync/etc/systemd/system/aurora-btsync.service %{buildroot}%{_unitdir}/aurora-btsync.service
ln -s aurora-btsync.service %{buildroot}%{_unitdir}/asahi-btsync.service
install -Dm644 aurora-btsync/etc/udev/rules.d/96-aurora-btsync.rules %{buildroot}%{_udevrulesdir}/96-aurora-btsync.rules
%make_install -C aurora-panel-nits BINDIR=%{_bindir} UNITDIR=%{_unitdir} UDEVDIR=%{_udevrulesdir}

%files
%license LICENSE
%{_bindir}/aurora-bless
%{_bindir}/asahi-bless

%post -n aurora-btsync
%systemd_post aurora-btsync.service

%preun -n aurora-btsync
%systemd_preun aurora-btsync.service

%files -n aurora-nvram
%license LICENSE
%doc aurora-nvram/README.md NEO.md
%{_bindir}/aurora-nvram
%{_bindir}/asahi-nvram

%files -n aurora-btsync
%license LICENSE
%doc aurora-btsync/README.md
%{_bindir}/aurora-btsync
%{_bindir}/asahi-btsync
%{_unitdir}/aurora-btsync.service
%{_unitdir}/asahi-btsync.service
%{_udevrulesdir}/96-aurora-btsync.rules

%files -n aurora-panel-nits
%license LICENSE
%doc aurora-panel-nits/README.md
%{_bindir}/aurora-panel-nits
%{_unitdir}/aurora-panel-nits.service
%dir %{_unitdir}/systemd-backlight@backlight:apple-panel-bl.service.d
%{_unitdir}/systemd-backlight@backlight:apple-panel-bl.service.d/50-aurora-panel-nits.conf
%{_udevrulesdir}/90-aurora-panel-nits.rules

%changelog
* Wed Nov 11 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.4.4-4
- Pin aurora-bless 9b47a178 and ship aurora-nvram and aurora-btsync, which
  replace asahi-nvram (0.2.3 panics on current NVRAM v3 stores) and
  asahi-btsync, with asahi-nvram and asahi-btsync symlinks and an
  asahi-btsync.service alias.
- aurora-btsync refreshes the keys of devices macOS paired again, writes
  [LongTermKey] for LE devices, parses the appearance tag, restarts
  bluetoothd through systemd and ignores connect timeouts; fixes for the
  problems reported and diagnosed by Ashwin Sawant (asahi-nvram issue 48).

* Wed Nov 11 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.4.4-3
- Pin aurora-bless 2707f610 and ship aurora-panel-nits: the built-in panel
  starts at the boot loader's NVRAM backlight-nits level, and the user's level
  is stored there (rate limited) instead of in systemd-backlight's file.

* Tue Nov 03 2026 Aurora Silicon <hey@djdev.me> - 0.4.4-2
- Pin aurora-bless 903a6304 (asahi-bless 0.4.4-neo.2, apple-nvram 0.4.0): Neo
  NVRAM writes work on GigaDevice flash and take the scoped write
  opt-in, so bless works on fresh installs.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
