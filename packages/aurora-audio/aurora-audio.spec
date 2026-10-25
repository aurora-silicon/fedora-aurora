%global commit 78803e1122a4f4a943b0e490eeb869db2537cd66
Name: aurora-audio
Version: 4.1
Release: 4%{?dist}
Summary: Aurora Apple Silicon audio DSP profiles
License: MIT
URL: https://github.com/aurora-silicon/asahi-audio
Source0: aurora-audio-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: make
# Fedora Asahi installs carry asahi-audio, which ships the same files.
Provides: asahi-audio = %{version}-%{release}
Conflicts: asahi-audio
Requires: alsa-ucm-conf-aurora pipewire pipewire-module-filter-chain-lv2 wireplumber bankstown lv2-triforce lsp-plugins-lv2 speakersafetyd speakerguardd

%description
Aurora Apple Silicon audio DSP profiles. Built from the recorded Aurora source revision.

%prep
%autosetup -n asahi-audio-78803e1122a4f4a943b0e490eeb869db2537cd66

%build

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%files
%license LICENSE
%{_datadir}/asahi-audio/
%{_datadir}/wireplumber/
%{_datadir}/pipewire/

%changelog
* Sat Oct 24 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-4
- Move to asahi-audio 78803e1: the J616s speaker graph and headphone jack
  priorities (aurora-silicon/asahi-audio#8), and the J700 speaker graph's
  +3 dB make-up gain with a brick-wall limiter (#7).
- Provide and conflict with asahi-audio, so a Fedora Asahi install can move
  to this package.

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 4.1-3
- Require PipeWire LV2 support to load the speaker DSP profiles.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
