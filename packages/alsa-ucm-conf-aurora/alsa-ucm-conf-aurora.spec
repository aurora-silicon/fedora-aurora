%global commit a270b2e2d705ed521b07d008aac45283c75fb986
Name: alsa-ucm-conf-aurora
Version: 10
Release: 3%{?dist}
Summary: Aurora ALSA use-case profiles
License: BSD-3-Clause
URL: https://github.com/aurora-silicon/alsa-ucm-conf-asahi
Source0: alsa-ucm-conf-aurora-%{commit}.tar.gz
BuildArch: noarch
Provides: alsa-ucm-asahi
Conflicts: alsa-ucm-asahi
Requires: alsa-ucm

%description
Aurora ALSA use-case profiles. Built from the recorded Aurora source revision.

%prep
%autosetup -n alsa-ucm-conf-asahi-a270b2e2d705ed521b07d008aac45283c75fb986

%build

%install
mkdir -p %{buildroot}%{_datadir}/alsa
cp -a ucm2 %{buildroot}%{_datadir}/alsa/

%files
%license LICENSE.asahi
%{_datadir}/alsa/ucm2/*

%changelog
* Thu Oct 29 2026 Ryan Murray <ryan@aurorasilicon.org> - 10-3
- Move to alsa-ucm-conf-asahi a270b2e: the 3-channel AOP microphone follows
  the lid's "Internal Mic Jack" (aurora-silicon/alsa-ucm-conf-asahi#8), so
  the M1 Pro and M2 hide the internal microphones while the lid is closed.
  Also brings the J616s high-quality microphone card (#7).

* Sat Oct 24 2026 Ryan Murray <ryan@aurorasilicon.org> - 10-2
- Move to alsa-ucm-conf-asahi 777d704: the J616s speaker and headphone jack
  cards (aurora-silicon/alsa-ucm-conf-asahi#5) and the J700 internal
  microphone following its jack (#4).

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
