%global commit c967141161bea3badc7754e23d80b39ffb1bdafd
Name: aurora-audio
Version: 4.1
Release: 14%{?dist}
Summary: Aurora Apple Silicon audio DSP profiles
License: MIT
URL: https://github.com/aurora-silicon/asahi-audio
Source0: aurora-audio-%{commit}.tar.gz
Source1: module-setup.sh
Patch0: 0001-restore-legacy-speaker-graphs.patch
BuildArch: noarch
BuildRequires: make
# Fedora Asahi installs carry asahi-audio, which ships the same files.
Provides: asahi-audio = %{version}-%{release}
Conflicts: asahi-audio
Requires: alsa-ucm-conf-aurora pipewire pipewire-module-filter-chain-lv2 wireplumber >= 0.5.16 bankstown lv2-triforce lsp-plugins-lv2
# Restore the established Asahi protection stack on existing installations.
Requires: speakersafetyd speakerguardd
Obsoletes: speakerguardd-v2 < 1.0.0~alpha.1-0.33
Obsoletes: speakerguardd-v2-selinux < 1.0.0~alpha.1-0.33
Conflicts: speakerguardd-v2 < 1.0.0~alpha.1-0.33

%description
Aurora Apple Silicon audio DSP profiles. Built from the recorded Aurora source revision.

%prep
%autosetup -p1 -n asahi-audio-c967141161bea3badc7754e23d80b39ffb1bdafd

%build

%check
make install DESTDIR="$PWD/check-root" PREFIX=/usr
for board in j316 j413 j616 j700; do
    test -s "check-root/usr/share/asahi-audio/$board/graph.json"
    grep -q "/usr/share/asahi-audio/$board/graph.json" check-root/usr/share/wireplumber/wireplumber.conf.d/99-asahi.conf
done
test -s check-root/usr/share/asahi-audio/j700/48.wav
rm -rf check-root

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}
install -Dm755 %{SOURCE1} %{buildroot}%{_prefix}/lib/dracut/modules.d/90aurora-audio/module-setup.sh

%files
%license LICENSE
%{_datadir}/asahi-audio/
%{_datadir}/wireplumber/
%{_datadir}/pipewire/
%{_prefix}/lib/dracut/modules.d/90aurora-audio/

%changelog
* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 4.1-14
- Retire only the speakerguardd v2 previews up to release candidate 7
  (1.0.0~alpha.1-0.32 and older), so release candidate 8 can be installed by
  hand beside aurora-audio. Nothing installs it by default.

* Sun Nov 08 2026 Aurora Silicon <hey@djdev.me> - 4.1-12
- Restore the shipped Asahi speaker DSP graphs and retire the v2 preview
  packages. Kernel 7.3.0-26 restores the legacy protection interface.
- Verify every restored speaker graph and the J700 FIR during the build.


* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-11
- Move to asahi-audio c967141: the microphone cards are hidden from
  clients (no dead "Microphone" port beside the mic graph), and the
  built-in card stays on HiFi with nothing in the jack (asahi-audio#24).

* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-10
- Move to asahi-audio a321ae9: no speaker graph for j316, j413, j616 and
  j700, whose speakers speakerguardd v2 now voices from the Mac's own
  Apple tuning (asahi-audio#22); also the true-peak limiter on every other
  board's speaker outputs (#17), the j293 rear-woofer ratio (#18) and the
  sweep distortion tool (#19).

* Fri Nov 06 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-9
- Require speakerguardd-v2 beside speakersafetyd and speakerguardd 0.1. Its
  fleet gate starts exactly one stack per boot; on a kernel without the v2
  interface (every fleet kernel today) that is the older daemons, as before.

* Thu Nov 05 2026 Michal S. <michal_stopyra@icloud.com> - 4.1-8
- Include the J614 microphone DSP graph and WirePlumber rule (asahi-audio#16).

* Fri Oct 30 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-7
- Move to asahi-audio d957fab: the built-in headphone sink of every Mac
  keeps the volume and mute the user set on it across boots, also with
  nothing plugged in (aurora-silicon/asahi-audio#15).
- Require WirePlumber 0.5.16 or later. Older versions lose the stored mute
  of the speaker filter sink at every boot.

* Wed Oct 28 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-6
- Carry snd-seq in the initramfs. appledrm brings snd-pcm there, and
  Fedora's dist-alsa.conf loads snd-seq with it, which failed at every boot.

* Wed Oct 28 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-5
- Move to asahi-audio f513878: the J616 and J700 microphone graphs boost
  to match the M1 and M2 graphs (aurora-silicon/asahi-audio#12), and every
  microphone graph presents its processed channel as MONO, so stereo
  clients hear it in both ears (#13).

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
