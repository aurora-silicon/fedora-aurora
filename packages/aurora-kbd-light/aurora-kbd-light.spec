%global commit 72c3bb35f28d60fbc2e6db0eb8933a669832f16f
Name: aurora-kbd-light
Version: 0.1.0
Release: 3%{?dist}
Summary: Keyboard backlight that follows the ambient light sensor
License: MIT
URL: https://github.com/aurora-silicon/kbd-light
Source0: https://github.com/aurora-silicon/kbd-light/archive/%{commit}/%{name}-%{commit}.tar.gz
Source1: 80-aurora-kbd-light.preset
Source2: 90-aurora-kbd-light.rules
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
# The unit's boot start can come before the keyboard backlight LED and the
# light sensor exist; udev starts it, if it is enabled, when either appears.
install -Dm644 %{SOURCE2} %{buildroot}%{_udevrulesdir}/90-aurora-kbd-light.rules

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
%{_udevrulesdir}/90-aurora-kbd-light.rules

%changelog
* Mon Nov 23 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-3
- Move to kbd-light 72c3bb35 (kbd-light#1), as Arch Linux ARM ships since
  alarm-aurora#336: optional idle dimming. With AURORA_KBD_LIGHT_IDLE_SECONDS
  set in /etc/default/aurora-kbd-light, the backlight fades to
  AURORA_KBD_LIGHT_IDLE_PERCENT (default 0) after that many seconds without
  a key press, and comes back at the next one. Off by default.

* Thu Nov 12 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-2
- Start the service, if it is enabled, when the keyboard backlight LED or the
  AOP light sensor appears; at boot its condition could be checked before
  either existed.

* Thu Nov 05 2026 DjDeveloperr <hey@djdev.me> - 0.1.0-1
- Package kbd-light 727076b83eb6: the keyboard backlight follows the ambient
  light sensor, and is off while the displays sleep.
