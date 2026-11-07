%global debug_package %{nil}
%global commit 21a8ab94bc34564c676be10d68be20a4d2e45f60
# Tagged release; preserve its label in the source archive build.
%global release_tag 1.0.0b6
# 1 once the pinned source has no monitor (aura#77); %%prep checks it. Such an aura
# moves the kernel into the CTXR window, so it requires a kernel built with
# CONFIG_ARM64_CTXR_EXECMEM, which kernel-aurora-core provides as aurora-ctxr-execmem.
%global monitor_free 1
Name: aura
Version: 1.0.0~b6
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
Requires: update-m1n1 aurora-stage2-ctxr-slot uboot-aurora
%if %{monitor_free}
Requires: aurora-ctxr-execmem
%endif

%description
Aurora bootloader for Apple Silicon. Built from the recorded Aurora source revision.

%prep
%autosetup -n aura-21a8ab94bc34564c676be10d68be20a4d2e45f60
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

%files
%license LICENSE 3rdparty_licenses/*
%{_libdir}/m1n1/
/usr/lib/asahi-boot/m1n1.bin
%{_datadir}/aura/

%changelog
* Sat Nov 07 2026 Diljit Singh <hey@djdev.me> - 1.0.0~b6-1
- Pin aura v1.0.0b6 (21a8ab94, aura#98). It has no monitor and runs Linux
  at EL2 in the CTXR window on M4 and later Macs (aura#77), so monitor_free
  is 1: ship /usr/share/aura/monitor-free and require aurora-ctxr-execmem.

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
