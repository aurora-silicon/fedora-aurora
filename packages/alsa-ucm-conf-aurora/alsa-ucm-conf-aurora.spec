%global commit 777d7048c444bf20b11830380cfd846cd2744ee0
Name: alsa-ucm-conf-aurora
Version: 10
Release: 2%{?dist}
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
%autosetup -n alsa-ucm-conf-asahi-777d7048c444bf20b11830380cfd846cd2744ee0

%build

%install
mkdir -p %{buildroot}%{_datadir}/alsa
cp -a ucm2 %{buildroot}%{_datadir}/alsa/

%files
%license LICENSE.asahi
%{_datadir}/alsa/ucm2/*

%changelog
* Sat Oct 24 2026 Ryan Murray <ryan@aurorasilicon.org> - 10-2
- Move to alsa-ucm-conf-asahi 777d704: the J616s speaker and headphone jack
  cards (aurora-silicon/alsa-ucm-conf-asahi#5) and the J700 internal
  microphone following its jack (#4).

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
