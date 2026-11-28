%global commit a8c68c27c448ff39c915b46b8d33c53f2c56b705
Name: aurora-audio
Version: 4.1
Release: 19%{?dist}
Summary: Aurora Apple Silicon audio profiles
License: MIT
URL: https://github.com/aurora-silicon/asahi-audio
Source0: aurora-audio-%{commit}.tar.gz
Source1: module-setup.sh
Source3: 99-aurora-speaker-irq.conf
Source4: aurora-speaker-stack
Source5: aurora-speaker-stack.8
Source6: README.md
# speakerguardd v2 drives every Mac's speakers from the Mac's own tuning: no
# speaker graph, speaker FIR or raw speaker volume lock is installed.
Patch0: 0001-install-no-speaker-graphs.patch
BuildArch: noarch
BuildRequires: make python3
# Fedora Asahi installs carry asahi-audio, which ships the same files.
Provides: asahi-audio = %{version}-%{release}
Obsoletes: asahi-audio < %{version}-%{release}
Conflicts: asahi-audio
Requires: alsa-ucm-conf-aurora alsa-utils pipewire pipewire-module-filter-chain-lv2 wireplumber >= 0.5.16 bankstown lv2-triforce lsp-plugins-lv2 python3
Requires(posttrans): python3
# speakerguardd v2 is the speaker protection: every install has this package,
# so it brings v2 and retires the Asahi stack (speakersafetyd, its Aurora
# profiles and speakerguardd 0.1) on the upgrade. The speakersafetyd
# Obsoletes match only the builds this repository shipped (2.0.1-1.fc*.aurora1
# and < 2.0.1-1, profiles < 1-2), not stock Fedora's 2.0.1-1.fc*, so a
# speakersafetyd a user installs via aurora-speaker-stack select speakersafetyd
# installs cleanly under DNF5 and is not removed again by the next upgrade.
Requires: speakerguardd-v2 >= 1.0.0~alpha.2-0.63 aurora-speaker-upgrade
Obsoletes: speakersafetyd = 2.0.1-1.fc44.aurora1
Obsoletes: speakersafetyd = 2.0.1-1.fc45.aurora1
Obsoletes: speakersafetyd < 2.0.1-1
Obsoletes: speakersafetyd-aurora-profiles < 1-2
Obsoletes: speakerguardd < 0.2
Conflicts: speakerguardd < 0.2
Obsoletes: speakerguardd-v2 < 1.0.0~alpha.1-0.33
Obsoletes: speakerguardd-v2-selinux < 1.0.0~alpha.1-0.33
Conflicts: speakerguardd-v2 < 1.0.0~alpha.1-0.33

%description
Aurora Apple Silicon audio profiles: the microphone DSP graphs, the headphone
jack and built-in card rules for WirePlumber, and the speaker PCM's period
interrupts. Built from the recorded Aurora source revision. The speakers are
speakerguardd v2's, which this package requires.

%prep
%autosetup -p1 -n asahi-audio-%{commit}

%build

%check
make install DESTDIR="$PWD/check-root" PREFIX=/usr
wp=check-root/usr/share/wireplumber/wireplumber.conf.d/99-asahi.conf
# No speaker graph, speaker FIR or speaker rule of the Asahi stack.
test -z "$(find check-root/usr/share/asahi-audio \( -name 'graph*.json' -o -name '*.wav' \) -print)"
if grep -Eq 'graph[^"/]*\.json|RawSpeakers|asahi-lock-volume' "$wp"; then
    echo '99-asahi.conf still creates or locks a speaker path' >&2; exit 1
fi
test ! -e check-root/usr/share/wireplumber/scripts/device/asahi-lock-volume.lua
# Every filter the rules create is installed: the microphone graphs.
for f in $(grep -o '/usr/share/asahi-audio/[^"]*' "$wp"); do
    test -s "check-root$f"
done
for board in j293 j313 j314 j316 j413 j415 j604 j614 j616 j700 j714; do
    test -s "check-root/usr/share/asahi-audio/$board/mic.json"
done
python3 -I %{SOURCE4} --help >/dev/null
rm -rf check-root

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}
install -Dm755 %{SOURCE1} %{buildroot}%{_prefix}/lib/dracut/modules.d/90aurora-audio/module-setup.sh
install -Dm644 %{SOURCE3} %{buildroot}%{_datadir}/wireplumber/wireplumber.conf.d/99-aurora-speaker-irq.conf
install -Dm755 %{SOURCE4} %{buildroot}%{_bindir}/aurora-speaker-stack
install -Dm644 %{SOURCE5} %{buildroot}%{_mandir}/man8/aurora-speaker-stack.8
cp -p %{SOURCE6} README.aurora-audio.md

%posttrans
%{_bindir}/aurora-speaker-stack migrate --on-upgrade || :

%files
%license LICENSE
%doc README.aurora-audio.md
%{_bindir}/aurora-speaker-stack
%{_mandir}/man8/aurora-speaker-stack.8*
%{_datadir}/asahi-audio/
%{_datadir}/wireplumber/
%{_datadir}/pipewire/
%{_prefix}/lib/dracut/modules.d/90aurora-audio/

%changelog
* Sat Nov 28 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-19
- Ship aurora-speaker-stack (CLI, man page, README) for the optional one-command
  speakersafetyd user opt-out (aurora-speaker-stack select speakersafetyd|sgv2,
  status, and interlock-apply for the per-bind kernel interlock), and run
  aurora-speaker-stack migrate --on-upgrade in %posttrans to mask legacy units
  unless the user explicitly opted out.
* Sat Nov 28 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-18
- speakerguardd v2 is the speaker stack of every install: require it and
  aurora-speaker-upgrade, and obsolete the speakersafetyd 2.0.1-1 and
  speakersafetyd-aurora-profiles 1-1 builds, speakerguardd 0.1 and
  asahi-audio, so an upgrade removes them. A speakersafetyd installed
  later on purpose is not obsoleted.
- Drop the patch that restored the Asahi speaker graphs, and install no
  speaker graph, speaker FIR or raw speaker volume lock for any Mac. A Mac
  that v2 does not qualify keeps its speakers at the kernel's floor.
- The microphone graphs, the headphone jack and built-in card rules, the
  speaker PCM's period interrupts and the dracut module stay.
- Drop aurora-audio-v2-cleanup: v2 is always installed now, so it never ran.

* Wed Nov 25 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-17
- Refresh to asahi-audio a8c68c27 (J604/J714 mics, J713/J714 audio rules); rebase legacy speaker graph patch.

* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 4.1-16
- Retire only the speakerguardd v2 previews up to release candidate 7
  (1.0.0~alpha.1-0.32 and older), so release candidate 8 can be installed by
  hand beside aurora-audio. Nothing installs it by default.

* Mon Nov 09 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-15
- The J616 (MacBook Pro 16-inch M4 Pro/Max) speaker PCM also wakes on
  period interrupts: its AOP speaker service raises one per period, and a
  chrony slew re-prepared the timer-scheduled sink 7 times (0 with this).

* Mon Nov 09 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-14
- Built-in speakers on the MCA transport (M1, M2, M3 families) run on the
  speaker PCM's period interrupts (api.alsa.disable-tsched): a chrony clock
  slew no longer re-prepares the timer-scheduled sink every ~0.6 s (audible
  dropouts at every boot). AOP speaker Macs are unchanged.

* Mon Nov 09 2026 Ryan Murray <ryan@aurorasilicon.org> - 4.1-13
- Remove the per-user PipeWire and WirePlumber links the speakerguardd v2
  preview left in ~/.config (they point into /run/speakerguardd-graph,
  which nothing creates without v2, so PipeWire logged an error at every
  login). Only links into that directory go, and only while v2 is not
  installed; /etc/speakerguardd and /var/lib/speakerguardd stay.

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
