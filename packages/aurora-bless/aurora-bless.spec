%global commit 2707f61078ce5c8a34dfc50d1db15d41afd8ee91
Name: aurora-bless
Version: 0.4.4
Release: 3%{?dist}
Summary: Apple Silicon startup volume selector with Neo NVRAM support
License: MIT
URL: https://github.com/aurora-silicon/aurora-bless
Source0: aurora-bless-%{commit}.tar.gz
ExclusiveArch: aarch64
Provides: asahi-bless
Conflicts: asahi-bless
BuildRequires: rust cargo make systemd-rpm-macros

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

%prep
%autosetup -n aurora-bless-2707f61078ce5c8a34dfc50d1db15d41afd8ee91

%build
cargo build --locked --release -p asahi-bless -p aurora-panel-nits

%check
cargo test --locked -p asahi-bless -p apple-nvram -p asahi-nvram -p aurora-panel-nits

%install
install -Dm755 target/release/asahi-bless %{buildroot}%{_bindir}/aurora-bless
ln -s aurora-bless %{buildroot}%{_bindir}/asahi-bless
%make_install -C aurora-panel-nits BINDIR=%{_bindir} UNITDIR=%{_unitdir} UDEVDIR=%{_udevrulesdir}

%files
%license LICENSE
%{_bindir}/aurora-bless
%{_bindir}/asahi-bless

%files -n aurora-panel-nits
%license LICENSE
%doc aurora-panel-nits/README.md
%{_bindir}/aurora-panel-nits
%{_unitdir}/aurora-panel-nits.service
%dir %{_unitdir}/systemd-backlight@backlight:apple-panel-bl.service.d
%{_unitdir}/systemd-backlight@backlight:apple-panel-bl.service.d/50-aurora-panel-nits.conf
%{_udevrulesdir}/90-aurora-panel-nits.rules

%changelog
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
