%global debug_package %{nil}
%global commit 5dcf62d0bf28e42c0e3f4ece44908643ffd40837
# 1 once the pinned source has no monitor (aura#77); %%prep checks it. Such an aura
# moves the kernel into the CTXR window, so it requires a kernel built with
# CONFIG_ARM64_CTXR_EXECMEM, which kernel-aurora-core provides as aurora-ctxr-execmem.
%global monitor_free 1
Name: aura
Version: 1.0.0~b13.1
Release: 1%{?dist}
Summary: Aurora bootloader for Apple Silicon
License: MIT AND GPL-2.0-only
URL: https://github.com/aurora-silicon/aura
Source0: aura-%{commit}.tar.gz
ExclusiveArch: aarch64
BuildRequires: clang llvm lld rust rust-src cargo make python3
Provides: m1n1 = 1.6.1
Conflicts: m1n1
# A Mach-O Mac needs the update-m1n1 that leaves boot.bin alone.
Requires: update-m1n1 >= 20261107
Requires: aurora-stage2-ctxr-slot uboot-aurora
%if %{monitor_free}
Requires: aurora-ctxr-execmem
%endif

%description
Aurora bootloader for Apple Silicon. Built from the recorded Aurora source revision.

%prep
%autosetup -n aura-5dcf62d0bf28e42c0e3f4ece44908643ffd40837
found=0
if [ -f src/ctxr_exec.c ] || [ ! -f src/monitor.c ]; then found=1; fi
if [ "$found" != %{monitor_free} ]; then
  echo "aura.spec: set monitor_free to $found, which the pinned source is" >&2
  exit 1
fi

%build
export RUSTC_BOOTSTRAP=1
make %{?_smp_mflags} BUILDSTD=1 RELEASE=1 CHAINLOADING=1 USE_CLANG=1 BUILTIN_LOGO=aurora %{?release_tag:AURA_VERSION_TAG=%{release_tag}}
mkdir -p ../aurora-stage1
cp build/aura.bin ../aurora-stage1/aura-raw.bin
cp build/aura.macho ../aurora-stage1/aura.macho
cp build/aura-boot.macho ../aurora-stage1/aura-boot.macho
make clean
# The secure-flavour Stage 1 that aurora-secboot stage1 build fills with the
# owner's key. Its built-in key, used only while the key block is unfilled, is a
# fresh one whose private half is never written down, so an unfilled image
# verifies nothing.
python3 -c 'import os, sys; sys.path.insert(0, "tools"); import secboot_sign; sys.stdout.buffer.write(secboot_sign.pubkey(os.urandom(32)))' > ../aurora-stage1/nobody.pub
make %{?_smp_mflags} BUILDSTD=1 RELEASE=1 CHAINLOADING=1 USE_CLANG=1 BUILTIN_LOGO=aurora SECBOOT=audit SECBOOT_FLAVOUR=secure SECBOOT_PUBKEY=../aurora-stage1/nobody.pub %{?release_tag:AURA_VERSION_TAG=%{release_tag}}
cp build/aura.bin ../aurora-stage1/aura-secure-raw.bin
make clean
make %{?_smp_mflags} BUILDSTD=1 RELEASE=1 CHAINLOADING=1 ESP_STAGE2=1 USE_CLANG=1 BUILTIN_LOGO=aurora %{?release_tag:AURA_VERSION_TAG=%{release_tag}}

%install
install -Dm644 build/aura.bin %{buildroot}%{_libdir}/m1n1/m1n1.bin
install -Dm644 build/aura.bin %{buildroot}/usr/lib/asahi-boot/m1n1.bin
# An aura without the monitor: update-m1n1 then stops writing boot.bin on Mach-O Macs.
%if %{monitor_free}
install -Dm644 /dev/null %{buildroot}%{_datadir}/aura/monitor-free
%endif
install -Dm644 ../aurora-stage1/aura-raw.bin %{buildroot}%{_datadir}/aura/stage1/aura-raw.bin
install -Dm644 ../aurora-stage1/aura-boot.macho %{buildroot}%{_datadir}/aura/stage1/aura-boot.macho
install -Dm644 ../aurora-stage1/aura.macho %{buildroot}%{_datadir}/aura/stage1/aura.macho
install -Dm644 ../aurora-stage1/aura-secure-raw.bin %{buildroot}%{_datadir}/aura/stage1/aura-secure-raw.bin
# aura's own Stage 1 and signing tools, for aurora-secboot stage1 build and stage2 sign.
for t in fill_stage1_config.py secboot_sign.py macho_boot_object.py; do
  install -Dm644 tools/$t %{buildroot}%{_datadir}/aura/tools/$t
done
install -Dm644 tools/recovery/enroll-stage1.sh %{buildroot}%{_datadir}/aura/tools/enroll-stage1.sh

%files
%license LICENSE 3rdparty_licenses/*
%{_libdir}/m1n1/
/usr/lib/asahi-boot/m1n1.bin
%{_datadir}/aura/

%changelog
* Fri Nov 13 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b13.1-1
- Update to aura 1.0.0b13.1 (v1.0.0b13.1, 5dcf62d0): 1.0.0b13 plus
  aura#213. The ESP Stage 2 starts a post-M4 ANS that the previous stage
  powered off (nvme.sart=) and hands it on running, so the embedded U-Boot
  finds NVMe after a 1.0.0b11 or later Stage 1.

* Fri Nov 13 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b13-1
- Update to aura 1.0.0b13 (v1.0.0b13, f0f180af): ADT DART tunables on
  every enabled DART (aura#208), T8140 gpu-fw-data (#204), MTE tag storage
  (#184), DWC3 shutdown retires transfers first (#196), Stage 1 .text right
  after .init (#202), T8132 encoder firmware handoff (#152), T6041 dcpext2
  (#166), T8142/T8152 macOS 27.2 GPU firmware (#192, #189) and the Mac mini
  debug-port warning (#176).

* Fri Nov 13 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b12.1-1
- Update to aura 1.0.0b12.1 (v1.0.0b12.1, 54678354): 1.0.0b12 plus
  tools/macho_boot_object.py --execute-window (aura#195), secboot_sign.py
  sign-image for aura Stage 2 images (#197) and a secure-flavour Stage 1
  that links with this toolchain (#200). The default Stage 1 and the ESP
  Stage 2 are 1.0.0b12's code.
- Ship the secure-flavour Stage 1 as aura/stage1/aura-secure-raw.bin, for
  aurora-secboot stage1 build. Its built-in key is a throwaway one, so an
  image whose key block is not filled verifies nothing.

* Fri Nov 13 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b12-2
- Ship aura's Stage 1 and signing tools under /usr/share/aura/tools, for
  aurora-secboot stage1 build and stage2 sign on an existing install. No
  secure-flavour Stage 1 image yet: with this toolchain a 1.0.0b12
  SECBOOT=audit Stage 1 reaches the DCP log buffer at 0x120000.

* Thu Nov 12 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b12-1
- Update to 1.0.0b12 (ea20cedb). The T8140 encoder handoff now enables the
  encoder's whole power-domain chain (aura#190): with the fabric power states
  in linux#1298 the chain to venc0_me1 is seven deep, and 1.0.0b11 left the
  MacBook Neo's encoder 0 disabled. Also the J604 AOP handoff (#149), J616s
  hibernation and S2R windows at EL2 (#148), J813 arm64.nomte (#183) and the
  26.7.x iBoot train mapped to 26.6.2 component handoffs.

* Thu Nov 12 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b11-1
- Update to aura 1.0.0b11 (v1.0.0b11, eca16db0). Since bd9f3e82: memory a device may
  still reach stays allocated after a DART or NVMe failure (aura#175), DART
  Gen3 invalidation timeouts and dart_free_l2() roots (#180), a watchdog
  reset for faults before wdt_disable() (#138), the M1 Pro and M2 encoder
  firmware handoff (#161), the T8140 encoder chosen from the ADT (#167),
  the T8140 SIO tables for DisplayPort audio (#122), M4 Max laptop USB 3
  (#147), and M5 Pro handoffs (#158, #159, #169, #171, #173, #179).
  Secure boot (#133) stays off in this build.

* Wed Nov 11 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b10-5
- Pin aura main bd9f3e82, labelled 1.0.0b10-gbd9f3e82 from the archive
  directory as it is not a release tag.
  Since 014a758b: an opt-in DT entry (apple,adt-dvfs) gets the PMP media
  performance request levels from the ADT, so the M1 Pro and M2 encoder vote
  with this Mac's own values (aura#150); the T8140 APCIe tables are published
  for an OS that powers ANS's PCIe block back (#112).

* Wed Nov 11 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b10-4
- Pin aura main 014a758b, labelled 1.0.0b10-g014a758b from the archive
  directory as it is not a release tag.
  Since 2296392f: Stage 1 keeps a 178 s watchdog over the boot until a host
  attaches or Stage 2 starts, so a Stage 1 that stops before Stage 2 resets
  instead of staying dark (aura#127); the high-speed USB proxy recovers from
  a bus reset or disconnect (#130) and starts every no-data status stage on
  XferNotReady (#139); T6000/T8112 get their PMP boot data on a node without
  the pmp alias (#88); aura-try one-shot trials for the boot= kernel (#82);
  the J604/J715 radio port and J604 MTP DAPF hand-off (#141, #137); the M5
  Pro (T6050) Linux boot and the shared ANS hand-off (#144), which also moves
  kboot and the remaining hypervisor code into the .init slot so Stage 1
  links with clang 22.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b10-3
- Pin aura main 2296392f, labelled 1.0.0b10-g2296392f from the archive
  directory as it is not a release tag.
  Since dab56f2f: Stage 1's payload scan ends at a Mach-O boot object's
  __PRELINK_INFO, so an unpadded Mach-O Stage 1 no longer hands
  m1n1.config-lost=1 to Stage 2, which made M3 boards drop all graphics
  (aura#134); the J613 native external display path behind its own
  opt-in (#86); T8142 secondaries keep their writable state out of CTRR_D
  and the GPU firmware's data is reserved (#100, #143).

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b10-2
- Pin aura main dab56f2f. It is not a release tag, so the build is labelled
  1.0.0b10-gdab56f2f from the archive directory. Since 21a70e6e: the
  T6040 boot core power-gates too (aura#119), the T8142 ISP accepts the
  macOS 27.0 firmware (#99), and a Recovery script enrolls a hand-built
  Stage 1 (#131). The source still has no monitor, so monitor_free stays 1.

* Mon Nov 09 2026 Diljit Singh <hey@djdev.me> - 1.0.0~b10-1
- Pin aura main 21a70e6e (aura#135), labelled 1.0.0b10 as its VERSION
  file is. Since b8: the M4 GPU and DCP handoffs on 26.6.2 firmware for
  every M4 Mac (b9: aura#106, #110), M4 PIODMA gated on firmware (#116),
  ACIO v2 USB4 routers kept with their tuning (#103), T6041 SIO tables
  (#120), the speaker assembly ID for the kernel (#121), the T8140 DCP
  power chain (#125), AOP motion calibration on T6000 and T8112 (#124),
  J713 external displays (#108), the T6041 display on J614C (#132), and
  aura-try trials that reboot when they cannot start their payload and
  keep U-Boot off the watchdog (#128, #129, #135). The source still has
  no monitor, so monitor_free stays 1.

* Sun Nov 08 2026 Diljit Singh <hey@djdev.me> - 1.0.0~b8-1
- Pin aura v1.0.0b8 (30e93e89, aura#105): 1.0.0b7 plus aura#104, which runs
  the T8132 storage and memory steps on every T8132 board, not only the
  J713, so the J604, J623, J624, J715 and J773g can read their internal
  disk. The source still has no monitor, so monitor_free stays 1.

* Sat Nov 07 2026 Diljit Singh <hey@djdev.me> - 1.0.0~b7-1
- Pin aura v1.0.0b7 (78bac92d, aura#102). It has no monitor and runs Linux
  at EL2 in the CTXR window on M4 and later Macs (aura#77), so monitor_free
  is 1: ship /usr/share/aura/monitor-free and require aurora-ctxr-execmem.

* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.0.0~b5-3
- Require trial-aware Stage 2 updates while retaining the CTXR slot contract.

* Fri Nov 06 2026 Diljit Singh <hey@djdev.me> - 1.0.0~b5-2
- Require the update-m1n1 that can write m1n1/boot-ctxr.bin on Mach-O Macs and
  leave m1n1/boot.bin as it is.
- Ship /usr/share/aura/monitor-free when the pinned source has no monitor. That
  is what turns those two behaviours on. monitor_free declares it, and %%prep
  refuses a source that disagrees.
- With monitor_free, require aurora-ctxr-execmem: a kernel that keeps its code
  inside the CTXR window this aura moves it into.

* Thu Nov 05 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 1.0.0~b5-1
- Pin aura v1.0.0b5 (9a173ff5): each SN012776 speaker amp gets its brownout,
  DC blocker, speaker-config and amp-tx-zd-config from the ADT (aura #75).
  Kernels with aurora-silicon/linux #981 need it for the speakers.

* Tue Nov 03 2026 Aurora Silicon <hey@djdev.me> - 1.0.0~b4-1
- Pin aura v1.0.0b4 (8b150963): the monitor decides by the probe on every
  chip, so Mach-O mode runs it on every M4-and-later Mac.

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 1.0.0~b3-1
- Pin aura v1.0.0b3 (1b4d11cb): opt-in FEAT_NV2 virtualization and PSCI on
  the MacBook Neo, the ANE firmware preload hand-off on the M4 Pro and
  A18 Pro, and a quiet console once the monitor runs the OS.
- Ship the Stage 1 Mach-O boot object as aura/stage1/aura-boot.macho, the
  form the installer boots on M4 and later Macs.

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 1.0.0~b2-1
- Pin aura v1.0.0b2 (241540a6), a VERSION-only bump over a9cad94e.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 1.0.0~b1-3
- Track aurora-silicon/aura main at a9cad94 (SMBIOS name without date,
  firmware updatable flag), the aura the J616s and Neo run.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 1.0.0~b1-2
- Track aurora-silicon/aura main at 32dccf0 (1.0.0b1-g32dccf02): the
  1.6 MB Stage 1 that M1 Pro iBoot accepts, ANS sleep before hand-off
  (NVMe after a warm reboot on M1/M2), board-matched Stage 2 trees, AVE
  firmware hand-off on the M4 Pro, motion calibration and SMBIOS identity.

* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 1.0.0~b1-1
- Update to aura 1.0.0b1 (tag v1.0.0b1, 0ca7bf8).
- aura is the shipping Stage 1 and Stage 2. Its version marker is
  ##aura_ver##; it still accepts payload records made for m1n1.

* Mon Oct 26 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-6
- Track aurora-silicon/aura main at ec4a6ab.
- Upstream head: Merge pull request #8 from AxxzyWasTaken/t6041-ans-reserve

* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-5
- Track aura main at 553b566.
- Keep the load header's relocation inside the relocation padding, so
  Stage 1 and Stage 2 no longer grow by a stray 64 KiB.

* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-4
- Track aura main at b9ad403.
- Include all of omacom m1n1 integration/aurora, integration/neo included.
- Chainload a combined MacBook Neo Stage 2 that reaches firmware RO.

* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-3
- Track aura main at 22bab60.
- Start the display on the 13-inch M1 MacBook Pro instead of timing out.
- Accept empty successful replies to display power, mode and surface requests.
- Keep display firmware memory mapped when the firmware does not stop.

* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-2
- Track aura main at 8f4ee88.
- Keep booting when the power table names a parent it does not list.
- Hand the M3 MacBook Air internal display over to the kernel when requested.
- Run an M1-M3 Stage 2 from above the chainloaded image.
- Restore secondary CPU start on older CPUs with locked reset vectors.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
