# CI test only (fedora-aurora#203), never merge.
%global commit 727076b83eb65b0162317a9e2fa0ba850df1f5ca
Name: aurora-kbd-light
Version: 0.1.0
Release: 1%{?dist}
Summary: Keyboard backlight that follows the ambient light sensor
License: MIT
URL: https://github.com/aurora-silicon/kbd-light
Source0: https://github.com/aurora-silicon/kbd-light/archive/%{commit}/%{name}-%{commit}.tar.gz
Source1: 80-aurora-kbd-light.preset
ExclusiveArch: aarch64
BuildRequires: gcc make systemd-rpm-macros

%description
Drives the keyboard backlight of an Apple silicon MacBook from its ambient
light sensor, the way macOS does: brightest in the dark, fading out as the
room gets brighter and off in daylight, and off with the lid closed or the
displays asleep. A change
made from the desktop's slider or by its idle dimming is respected. Settings
are in /etc/default/aurora-kbd-light.

%prep
%autosetup -n kbd-light-%{commit}

%build
%make_build CFLAGS="%{optflags}" LDFLAGS="%{build_ldflags}"

%install
%make_install PREFIX=%{_prefix} UNITDIR=%{_unitdir}
# On for every Mac, like the keyboard backlight on macOS.
install -Dm644 %{SOURCE1} %{buildroot}%{_presetdir}/80-aurora-kbd-light.preset

%post
%systemd_post aurora-kbd-light.service
%preun
%systemd_preun aurora-kbd-light.service
%postun
%systemd_postun_with_restart aurora-kbd-light.service

%files
%license LICENSE
%doc README.md
%{_bindir}/aurora-kbd-light
%{_unitdir}/aurora-kbd-light.service
%{_presetdir}/80-aurora-kbd-light.preset

%changelog
* Thu Nov 05 2026 DjDeveloperr <hey@djdev.me> - 0.1.0-1
- Package kbd-light 727076b83eb6: the keyboard backlight follows the ambient
  light sensor, and is off while the displays sleep.
