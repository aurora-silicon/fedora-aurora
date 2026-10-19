%global commit b2da7512e9bfcd5837355d2393f3c43219acf6b9
Name: aurora-audio
Version: 4.1
Release: 3%{?dist}
Summary: Aurora Apple Silicon audio DSP profiles
License: MIT
URL: https://github.com/aurora-silicon/asahi-audio
Source0: aurora-audio-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: make
Requires: alsa-ucm-conf-aurora pipewire pipewire-module-filter-chain-lv2 wireplumber bankstown lv2-triforce lsp-plugins-lv2 speakersafetyd speakerguardd

%description
Aurora Apple Silicon audio DSP profiles. Built from the recorded Aurora source revision.

%prep
%autosetup -n asahi-audio-b2da7512e9bfcd5837355d2393f3c43219acf6b9

%build

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%files
%license LICENSE
%{_datadir}/asahi-audio/
%{_datadir}/wireplumber/
%{_datadir}/pipewire/

%changelog
* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 4.1-3
- Require PipeWire LV2 support to load the speaker DSP profiles.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
