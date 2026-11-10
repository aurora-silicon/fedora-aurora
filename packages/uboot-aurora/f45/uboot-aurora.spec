%global debug_package %{nil}
%global commit 6363e77fe6287b79219a4d06947b0076bdd765fb
Name: uboot-aurora
Version: 2026.07
Release: 11%{?dist}
Summary: Aurora U-Boot for Apple Silicon
License: GPL-2.0-or-later
URL: https://github.com/aurora-silicon/u-boot
Source0: uboot-aurora-%{commit}.tar.gz
ExclusiveArch: aarch64
Provides: uboot-images-armv8
Conflicts: uboot-images-armv8
BuildRequires: gcc make bc bison flex dtc python3 python3-pyelftools swig openssl3-devel openssl3-devel-engine gnutls-devel

%description
Aurora U-Boot for Apple Silicon. Built from the recorded Aurora source revision.

%prep
%autosetup -n u-boot-6363e77fe6287b79219a4d06947b0076bdd765fb

%build
make O=build-aurora apple_m1_defconfig
make O=build-aurora %{?_smp_mflags}

%install
install -Dm644 build-aurora/u-boot-nodtb.bin %{buildroot}%{_datadir}/uboot/apple_m1/u-boot-nodtb.bin
install -Dm644 build-aurora/u-boot-nodtb.bin %{buildroot}/usr/lib/asahi-boot/u-boot-nodtb.bin

%files
%license Licenses/gpl-2.0.txt
%{_datadir}/uboot/apple_m1/
/usr/lib/asahi-boot/u-boot-nodtb.bin

%changelog
* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 2026.07-11
- Track U-Boot aurora-wip at 6363e77. On M4 and later Macs a zboot kernel
  is decompressed into the CTXR window and boots there on all CPUs
  (u-boot#45); before, the EFI stub placed it outside the window and only
  the boot CPU came up. Also: Apple NVMe command fixes (u-boot#26), the
  J604 keyboard MTP left to Linux (#44) and the J613 MTP live handoff (#30).

* Mon Nov 09 2026 Diljit Singh <hey@djdev.me> - 2026.07-10
- Track U-Boot aurora-wip at 48c6b2c (u-boot#42). The M4 Max (T6041)
  boots like the M4 Pro (u-boot#42), and the T6050 (M5 Max, J714c) boots
  from NVMe by adopting the ANS session an m1n1 Stage 2 hands over
  (u-boot#41); without /chosen/asahi,nvme-adopt nothing changes.

* Sat Nov 07 2026 Aurora Silicon <hey@djdev.me> - 2026.07-9
- Track U-Boot aurora-wip at e1ef8b6. On M4 and later Macs it loads the
  kernel and the EFI runtime code into the CTXR window, and keeps
  device-tree reservations out of it (u-boot#32, #36). Also the J713
  external DCP handoff, speaker amps and ISP handoff (u-boot#31, #34, #35).

* Thu Nov 05 2026 Michal S. <michal_stopyra@icloud.com> - 2026.07-8
- Include the merged J614s retained MTP input handoff (u-boot#29).

* Mon Nov 02 2026 Ryan Murray <ryan@aurorasilicon.org> - 2026.07-7
- Build host signing tools with Fedora 45's OpenSSL 3 compatibility development
  packages, retaining ENGINE support without changing the target configuration.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 2026.07-6
- Track U-Boot aurora-wip at d30213e (u-boot PR 28 merged: boot speed,
  boot timings, SMBIOS identity, quiet boot), the U-Boot all four Aurora
  Macs run. Release 5 was rebuilt from an older pin by mistake.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 2026.07-5
- Track U-Boot aurora-wip at 01f255b: DRAM ranges in one device-tree pass,
  USB-C left to the OS on machines with a built-in keyboard (M1 Pro dock),
  and the J713 FDT size limit.

* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 2026.07-4
- Track U-Boot aurora-wip at 2409ad5, the U-Boot that ships with
  aura 1.0.0b1.
- MacBook Pro M4 Pro (J616s, T6040) boot support, NVMe included.
- Boot from the ESP that holds the EFI boot loader, without a serial
  console or a countdown on the Aurora EFI path.
- Name the SPI keyboard spikbd in stdin, and start the MacBook Neo
  keyboard before autoboot.
- MacBook Air M4 (J713): carry the SEP boot manifests and AOP
  reservations into the OS tree.

* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 2026.07-3
- Track U-Boot aurora-wip at 7680260.
- MacBook Neo: answer the firmware of the adopted NVMe session, expose only
  the main namespace, and reset the controller when a command never
  completes, so that GRUB searching every disk no longer wedges the queue.
- Start the console with the 16x32 font on HiDPI panels, for U-Boot and
  GRUB's text menu.
- MacBook Air M4 (J713) boot support; other Macs keep booting if its
  handoff step fails.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
