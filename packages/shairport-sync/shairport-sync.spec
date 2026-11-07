%global commit 0b1c4391ffd398e7b145eb4b98416261380adeea
# Aurora 2026-10-25: Fedora's shairport-sync 4.3.7 spec with AirPlay 2 turned on, for synced
# multi-room AirPlay on the Aurora receivers (Ryan). Differences from Fedora's spec:
#   - --with-airplay-2 and its build dependencies, all from Fedora (libavcodec-free, not
#     RPM Fusion; Fedora's own note said AirPlay 2 needed libavcodec-freeworld, %check below
#     proves libavcodec-free has the float planar AAC decoder 4.3.7 needs);
#   - Patch0 lets 4.3.7 read nqptp 1.2.9's smi11 shared memory (see the patch's header);
#   - Patch1 ports the AAC capability check to avcodec_get_supported_config() (FFmpeg 9, F45);
#   - Patch2 adds general.airplay_model, the advertised model identifier (picker glyph);
#   - Requires nqptp(smi) = 11;
#   - Release sorts above Fedora's 4.3.7-3.fc44 and 4.3.7-5.fc45, so it upgrades over them;
#     aurora-repos' vendor policy lets the Aurora build replace Fedora's.
Name:           shairport-sync
Version:        4.3.7
Release:        6%{?dist}.aurora.ap2.6
Summary:        AirTunes emulator. Multi-Room with Audio Synchronisation (AirPlay 2 build)
# MIT licensed except for tinysvcmdns under BSD,
# FFTConvolver/ under GPLv3+ and audio_sndio.c
# under ISC
# Automatically converted from old format: MIT and BSD and GPLv3+ and ISC - review is highly recommended.
License:        LicenseRef-Callaway-MIT AND LicenseRef-Callaway-BSD AND GPL-3.0-or-later AND ISC
URL:            https://github.com/mikebrady/shairport-sync
# Upstream tag 4.3.7 (0b1c4391ffd3), pinned in sources.json; same tree as Fedora's Source0.
Source0:        %{name}-%{commit}.tar.gz
Patch0:         shairport-sync-4.3.7-nqptp-smi11.patch
Patch1:         shairport-sync-4.3.7-ffmpeg9-supported-config.patch
Patch2:         shairport-sync-4.3.7-airplay-model.patch

%{?systemd_requires}
Requires: avahi
Requires: nqptp(smi) = 11
BuildRequires: make
BuildRequires:  systemd
BuildRequires:  pkgconfig(libconfig)
BuildRequires:  pkgconfig(popt)
BuildRequires:  pkgconfig(openssl)
BuildRequires:  pkgconfig(libdaemon)
BuildRequires:  pkgconfig(avahi-core)
BuildRequires:  pkgconfig(alsa)
BuildRequires:  pkgconfig(soxr)
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:	gcc
BuildRequires:	gcc-c++
BuildRequires:	pkgconfig(libpulse)
BuildRequires:	pkgconfig(libpipewire-0.3)
# airplay2 support, Fedora packages only
BuildRequires:  pkgconfig(uuid)
BuildRequires:  libavcodec-free-devel
BuildRequires:  libavformat-free-devel
BuildRequires:  libavutil-free-devel
BuildRequires:  libswresample-free-devel
BuildRequires:  pkgconfig(libgcrypt)
BuildRequires:  pkgconfig(libsodium)
BuildRequires:  pkgconfig(libplist-2.0)
BuildRequires:  xxd

%description
Shairport Sync emulates an AirPort Express for the purpose of streaming audio
 from iTunes, iPods, iPhones, iPads and AppleTVs. Audio played by a Shairport
 Sync-powered device stays synchronised with the source and hence with similar
 devices playing the same source. Thus, for example, synchronised multi-room
 audio is possible without difficulty. (Hence the name Shairport Sync, BTW.)

Shairport Sync does not support AirPlay video or photo streaming.

This build has AirPlay 2 enabled. It needs nqptp running for timing.

%prep
%autosetup -n shairport-sync-%{commit} -p1

# Create a sysusers.d config file
cat >shairport-sync.sysusers.conf <<EOF2
u shairport-sync - '%{name} User' %{_sharedstatedir}/%{name} -
m shairport-sync audio
EOF2

%build
autoreconf -i -f
%configure --sysconfdir=/etc --with-alsa --with-pipe --with-dummy \
           --with-stdout --with-pa --with-metadata --with-pw \
           --with-soxr --with-avahi --with-systemd --with-ssl=openssl \
           --with-create-user-group=false --with-airplay-2

%make_build

%install
%make_install
rm %{buildroot}/etc/shairport-sync.conf.sample
mkdir -p %{buildroot}/%{_sharedstatedir}/%{name}

install -m0644 -D shairport-sync.sysusers.conf %{buildroot}%{_sysusersdir}/shairport-sync.conf

%check
# -V and -h only count as the first argument (anything else starts the daemon), so keep them first.
v=$(timeout 20 %{buildroot}%{_bindir}/shairport-sync -V)
echo "version string: $v"
case "$v" in 4.3.7-AirPlay2-smi11-*) ;; *) echo "not an AirPlay 2 smi11 build"; exit 1 ;; esac
for f in OpenSSL Avahi ALSA pa pw soxr metadata; do echo "$v" | tr '-' '\n' | grep -qx "$f" || { echo "missing $f"; exit 1; }; done
# 4.3.7 refuses to start in AirPlay 2 mode without a float planar AAC decoder and says so in -h.
grep -q -a 'general.airplay_model' %{buildroot}%{_bindir}/shairport-sync || { echo "Patch2 missing"; exit 1; }
if timeout 20 %{buildroot}%{_bindir}/shairport-sync -h | grep -q 'IMPORTANT NOTE'; then
  echo "libavcodec has no fltp AAC decoder"; exit 1
fi

%post
%systemd_post %{name}.service

%preun
%systemd_preun %{name}.service

%postun
%systemd_postun_with_restart %{name}.service

%files
%config(noreplace) /etc/shairport-sync.conf
/usr/bin/shairport-sync
/usr/share/man/man1/shairport-sync.1.gz
%{_unitdir}/%{name}.service
%doc README.md RELEASENOTES.md TROUBLESHOOTING.md AIRPLAY2.md
%license LICENSES
%attr(-, %{name}, %{name}) %{_sharedstatedir}/%{name}
%{_sysusersdir}/shairport-sync.conf

%changelog
* Tue Nov 03 2026 Aurora Silicon <noreply@aurorasilicon.org> - 4.3.7-6.aurora.ap2.6
- Build in fedora-aurora for Fedora 44 and 45 (the receivers ran local ap2.3/ap2.4 builds)
- Drop the ap2.5 manufacturer experiment (Patch3); same sources and patches as ap2.4
- Vendor comes from the shared builder

* Sun Oct 25 2026 Aurora Silicon <noreply@aurorasilicon.org> - 4.3.7-6.aurora.ap2.5
- Patch3 (experiment): /info manufacturer "Apple Inc." when general.airplay_model is set

* Sun Oct 25 2026 Aurora Silicon <noreply@aurorasilicon.org> - 4.3.7-6.aurora.ap2.4
- Patch2: general.airplay_model sets the advertised model identifier (unset = "Shairport Sync")

* Sun Oct 25 2026 Aurora Silicon <noreply@aurorasilicon.org> - 4.3.7-6.aurora.ap2.3
- Vendor: Aurora Silicon (the package had no vendor, which dnf5 refused to swap in for Fedora's)

* Sun Oct 25 2026 Aurora Silicon <noreply@aurorasilicon.org> - 4.3.7-6.aurora.ap2.2
- Patch1: AAC capability check through avcodec_get_supported_config() (FFmpeg 9 removed
  AVCodec.sample_fmts); built on both Fedora 44 and 45

* Sun Oct 25 2026 Aurora Silicon <noreply@aurorasilicon.org> - 4.3.7-6.aurora.ap2.1
- AirPlay 2 build against Fedora's libavcodec-free, for synced multi-room playback
- Patch0: read nqptp 1.2.9's smi11 shared memory (upstream never tested 4.3.7 with smi11)
- Requires nqptp(smi) = 11

* Fri Jul 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 4.3.7-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jun 12 2026 Yaakov Selkowitz <yselkowi@redhat.com> - 4.3.7-4
- Rebuilt for openssl 4.0

* Sat Jan 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 4.3.7-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Wed Dec 17 2025 Tom Callaway <spot@fedoraproject.org> - 4.3.7-2
- rebuild for new libconfig

* Fri Jul 25 2025 Fedora Release Engineering <releng@fedoraproject.org> - 4.3.7-1
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Tue Mar 04 2025 Bill Peck <bpeck@redhat.com> - 4.3.7-0
- Disable airplay2, Unfortantely airplay2 support requires libavcodec-freeworld
