%global commit 9219565939723cd5bc381941bc3978d52610d753
%global krel %{version}-%{release}.aarch64
%global debug_package %{nil}
# modules_install signs every module (CONFIG_MODULE_SIG_ALL) after
# INSTALL_MOD_STRIP has stripped it. rpm's strip passes would rewrite each .ko
# and drop the appended signature, so they are off; %%check verifies them.
%global __brp_strip %{nil}
%global __brp_strip_comment_note %{nil}
%global __brp_strip_lto %{nil}
# 1 with a kernel pin whose configuration resolves CONFIG_ARM64_CTXR_EXECMEM=y
# (aurora-silicon/linux#985), which keeps every kernel code page inside the CTXR
# window an aura without the monitor moves the kernel into. kernel-aurora-core
# then provides aurora-ctxr-execmem, which that aura requires. %%build checks it.
%global ctxr_execmem 1
Name: kernel-aurora
Version: 7.3.0
Release: 36%{?dist}.aurora
Summary: Aurora kernel for Apple Silicon Macs
License: GPL-2.0-only
URL: https://github.com/aurora-silicon/linux
Source0: kernel-aurora-%{commit}.tar.gz
Source1: config
Source4: fedora.config
Source5: validate-config.py
Source6: dtb-abi
ExclusiveArch: aarch64
BuildRequires: make gcc gcc-c++ clang llvm lld rust rust-src rustfmt cargo bindgen-cli
BuildRequires: bc bison flex dtc openssl openssl-devel elfutils-libelf-devel dwarves cpio perl python3 patch
Requires: kernel-aurora-core = %{version}-%{release}
Requires: kernel-aurora-modules-extra = %{version}-%{release}
# Not versioned: older installed kernels must not hold back its updates.
Requires: aurora-userpages
Provides: kernel-16k = %{version}-%{release}
Provides: installonlypkg(kernel)

%description
The Aurora kernel source and shared configuration for supported Apple Silicon
Macs, including MacBook Neo. Matching DTBs and modules are built together.

%package core
Summary: Aurora kernel image and device trees
Requires: coreutils kmod dracut grubby
# A kernel-only upgrade must also restore the legacy speaker graphs.
Requires: aurora-audio >= 4.1-12
Requires: (aurora-platform-core >= 44-23 if aurora-platform-core)
Requires: update-m1n1 >= 20261107
# sep-key interfaces 3 and 4 (linux#1506, #1544): aurora-fido before 0.2.0-2
# speaks only 1 and 2 and crash-loops against this kernel.
Conflicts: aurora-fido < 0.2.0-2
# SN012776 amp settings come from the DT that aura 1.0.0b5 fills in
# (https://github.com/aurora-silicon/linux/pull/981,
# https://github.com/aurora-silicon/aura/pull/75); under an older Stage 2
# the speakers stay off.
Requires: aura >= 1.0.0~b12
Provides: kernel-uname-r = %{krel}
%if %{ctxr_execmem}
Provides: aurora-ctxr-execmem
%endif
Provides: installonlypkg(kernel)
Provides: kernel-16k-core = %{version}-%{release}

%description core
Aurora kernel image and device trees for Fedora's kernel-install boot pipeline.

%package modules-extra
Summary: Matching Aurora kernel modules
Requires: kernel-aurora-core = %{version}-%{release}
Provides: kernel-modules-uname-r = %{krel}
Provides: installonlypkg(kernel)
Provides: kernel-16k-modules-extra = %{version}-%{release}

%description modules-extra
Matching modules for the Aurora kernel.

%package -n aurora-userpages
Summary: Run programs with 4K userspace pages on the Aurora kernel
Requires: grubby

%description -n aurora-userpages
The userpages launcher runs a program and its descendants with another
userspace page size, such as 4K pages on the 16K Aurora kernel:
userpages 4k COMMAND. It is built from the kernel source, whose private
prctl interface it uses. Installing it adds user4k=on to the kernel command
line; an owner's user4k=off is kept.

%prep
%autosetup -p1 -n linux-%{commit}
cp %{SOURCE1} .config
scripts/kconfig/merge_config.sh -m .config arch/arm64/configs/asahi.config %{SOURCE4}
scripts/config --set-str LOCALVERSION '' --disable LOCALVERSION_AUTO --set-str SYSTEM_TRUSTED_KEYS '' --set-str SYSTEM_REVOCATION_KEYS ''

%build
export ARCH=arm64 RUSTC_BOOTSTRAP=1
export RUST_LIB_SRC=/usr/lib/rustlib/src/rust/library
# Build the pinned, corrected generator. It independently compiles its fixtures.
python3 tools/aurora-bindgen/build.py --output-dir "$PWD/private-bindgen"
export BINDGEN="$PWD/private-bindgen/rust-bindgen-0.73.2/target/release/bindgen"
make LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" olddefconfig
python3 %{SOURCE5} arch/arm64/configs/asahi.config %{SOURCE4} .config
ctxr=0
if grep -qx 'CONFIG_ARM64_CTXR_EXECMEM=y' .config; then ctxr=1; fi
if [ "$ctxr" != %{ctxr_execmem} ]; then
  echo "kernel-aurora.spec: set ctxr_execmem to $ctxr, which this pin's configuration resolves to" >&2
  exit 1
fi
make LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" rustavailable
make LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" %{?_smp_mflags} Image modules dtbs
[ "$(make -s LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" kernelrelease)" = "%{krel}" ]
# The launcher includes this tree's prctl.h, so its numbers match the kernel.
make -C tools/aurora-userpages

%install
export ARCH=arm64 RUSTC_BOOTSTRAP=1
make LLVM=1 LOCALVERSION=-%{release}.aarch64 INSTALL_MOD_PATH=%{buildroot}/usr INSTALL_MOD_STRIP=1 modules_install
install -Dm644 arch/arm64/boot/Image %{buildroot}/usr/lib/modules/%{krel}/vmlinuz
install -m644 .config %{buildroot}/usr/lib/modules/%{krel}/config
install -m644 System.map %{buildroot}/usr/lib/modules/%{krel}/System.map
install -m644 %{SOURCE6} %{buildroot}/usr/lib/modules/%{krel}/dtb-abi
mkdir -p %{buildroot}/usr/lib/modules/%{krel}/dtb/apple
cp arch/arm64/boot/dts/apple/*.dtb %{buildroot}/usr/lib/modules/%{krel}/dtb/apple/
rm -f %{buildroot}/usr/lib/modules/%{krel}/build %{buildroot}/usr/lib/modules/%{krel}/source
find %{buildroot}/usr/lib/modules/%{krel} -type f -name '*.ko' > modules.files
sed -i 's@%{buildroot}@@' modules.files
find %{buildroot}/usr/lib/modules/%{krel} -maxdepth 1 -type f ! -name vmlinuz ! -name config ! -name System.map ! -name dtb-abi >> metadata.files
sed -i 's@%{buildroot}@@' metadata.files
install -Dm755 tools/aurora-userpages/userpages %{buildroot}%{_bindir}/userpages
%{__strip} %{buildroot}%{_bindir}/userpages
install -Dm644 tools/aurora-userpages/README.rst %{buildroot}%{_docdir}/aurora-userpages/README.rst

%check
# Every installed module must still carry its signature.
unsigned=$(find %{buildroot}/usr/lib/modules/%{krel} -name '*.ko' -exec sh -c 'tail -c 28 "$1" | grep -q "~Module signature appended~" || echo "$1"' _ {} \; | head -5)
if [ -n "$unsigned" ]; then
  echo "kernel-aurora.spec: unsigned modules: $unsigned" >&2
  exit 1
fi

%posttrans core
if [ -x /usr/bin/kernel-install ]; then
  /usr/bin/kernel-install add %{krel} /usr/lib/modules/%{krel}/vmlinuz || exit 1
fi

%preun core
if [ -x /usr/bin/kernel-install ]; then
  /usr/bin/kernel-install remove %{krel} || :
fi

%posttrans -n aurora-userpages
# Images are built with user4k=on; add it to an installed system's boot
# entries and future kernels. Any user4k= the owner has set stays.
if [ -f /etc/kernel/cmdline ] && ! grep -qE '(^|[[:space:]])user4k=' /etc/kernel/cmdline; then
  grubby --update-kernel=ALL --args=user4k=on || :
fi

%files
%license COPYING

%files core -f metadata.files
%dir /usr/lib/modules/%{krel}
/usr/lib/modules/%{krel}/vmlinuz
/usr/lib/modules/%{krel}/config
/usr/lib/modules/%{krel}/System.map
/usr/lib/modules/%{krel}/dtb-abi
/usr/lib/modules/%{krel}/dtb/

%files modules-extra -f modules.files
%dir /usr/lib/modules/%{krel}/kernel

%files -n aurora-userpages
%license COPYING
%{_bindir}/userpages
%{_docdir}/aurora-userpages/

%changelog
* Thu Nov 12 2026 Ryan Murray <ryan@aurorasilicon.org> - 7.3.0-36
- Pin integration/aurora 92195659 (linux#1663), 29 merges (111 commits)
  after 2b05915f:
  - MacBook Neo (T8140): the AVE complex is now the parent power domain of
    the video encoders and the PMC VENC cluster vote (#1663). With encoder 0
    enabled by aura, the first wake from suspend-to-RAM no longer resets the
    Mac. Also a faster DRAM-kept wake with the PHY set up again
    after a deep sleep (#1658), the internal panel lit from the resume
    (#1631), SoC fabric power states (#1298), the second encoder described
    (#1626) and SIO AES revision 5 (#1622).
  - Display: firmware-27 HDR brightness hints, PQ with DSC, default RGB for
    SDR and VRR pairing on externals (#1614, #1641, #1640, #1613); A500 and
    500 thunk build fixes (#1629, #1630).
  - GPU and media: G17 25G83 channel-error and tiling fixes (#1662, #1644),
    ProRes on T6050 and T6041 (#1586, #1260), JPEG and scaler engines on more
    SoCs (#1617, #1616), J613 ISP preview (#974), T600x ANE hang recovery
    (#1660).
  - Boot chain: the lockdown LSM is built and started early, so secure-path
    boots raise lockdown to integrity by themselves; other boots stay at none
    (#1636).
  - Other: J716c USB4 display routing and GPU handoff (#1273, #1276), J616s
    panel bus and TMP103 read-only (#1642), J316s NFC (#1621), J614c/J616c
    ANE and JPEG (#1467), quieter boot warnings (#1623, #1635).
- config and fedora.config are unchanged. asahi.config now sets
  CONFIG_I2C_DP855=m, CONFIG_SENSORS_TMP103=m and the lockdown LSM
  (CONFIG_SECURITY_LOCKDOWN_LSM=y, _EARLY=y, LOCK_DOWN_KERNEL_FORCE_NONE=y,
  CONFIG_APPLE_AURORA_BOOT_SECURITY_LOCKDOWN=y), which selects
  CONFIG_MODULE_SIG=y: modules are signed with a per-build key, so the
  build needs the openssl tool. rpm's strip passes are off so the
  signatures survive, and %%check verifies every module is signed.
- Require aura 1.0.0~b12 or later: with #1298's fabric power states, 1.0.0~b11
  cannot enable the MacBook Neo's encoder 0 (aura#190).
  vmlinuz stays the raw Image, and dtb-abi is unchanged (generation 1).

* Thu Nov 12 2026 Ryan Murray <ryan@aurorasilicon.org> - 7.3.0-35
- Require aura 1.0.0~b11 or later. On the MacBook Neo this kernel's DT
  leaves the video encoder for aura to enable from the ADT (aura#167), and
  its DisplayPort audio needs the T8140 SIO tables (aura#122).

* Thu Nov 12 2026 Diljit Singh <hey@djdev.me> - 7.3.0-34
- Pin integration/aurora 2b05915f (linux#1445), 68 merges (341 commits)
  after 84d091f7:
  - MacBook Neo (T8140): suspend-to-RAM at EL2 with the DRAM-kept wake
    (#1445, which carries #1208-#1443), the ISP powered only while the
    camera streams (#1580), DisplayPort audio (#1280), UART0 (#1574) and
    the MTP transmit lock (#1010).
  - M5 Pro/Max (T6050): Neural Engine (#1595), video encoder and decoder
    (#1597, #1577), Touch ID (#1587), speakers and microphones (#1554,
    #1557), AOP sensors (#1521, #1542, #1548), the SD reader (#1570), the
    haptic actuator (#1576) and firmware-27 HDR on external displays
    (#1600).
  - M5 MacBook Air (T8142): GPU on firmware 27 (#1413), sound (#1423,
    #1533), Bluetooth (#1529), and panel, CPU and SEP fixes (#1528, #1531,
    #1535, #1536, #1537).
  - Shared: ISP IPC containment (#1560), SEP request-path log rate limits
    (#1578, #1590), the SIO AES skcipher (#1572), the PIODMA dmaengine
    (#1562), T6041 USB3 and DP audio (#1472, #1473, #1476) and the PMP's
    idle accounting without cpufreq (#1594).
- config and fedora.config are unchanged. asahi.config now sets
  CONFIG_APPLE_SOC_SLEEP=y and CONFIG_RTC_DRV_APPLE_PMU=y (was m); olddefconfig
  adds CONFIG_APPLE_PIODMA=m, CONFIG_APPLE_CLUSTER_PWRGATE=y,
  CONFIG_SND_SOC_APPLE_T8152_AOP_AUDIO=m and CONFIG_CRYPTO_DEV_APPLE_SIO_AES=m.
  vmlinuz stays the raw Image, and dtb-abi is unchanged (generation 1).

* Thu Nov 12 2026 Ryan Murray <ryan@aurorasilicon.org> - 7.3.0-33
- Pin integration/aurora 84d091f7 (linux#1519), 21 merges (109 commits)
  after 451dc709:
  - SEP and Touch ID: password-keyed per-user key bags (#921), and
    /dev/sep-key gains CANCEL and releases sealed secrets only after a
    touch (#1506).
  - Boot chain: the boot chain record is reported in
    /sys/firmware/aurora/boot_security, with integrity lockdown when the
    firmware reports an enforced chain (#1344,
    CONFIG_APPLE_AURORA_BOOT_SECURITY=y by default).
  - Media: the AVE temporal filter (MCTF) node with its T8140 DART stream
    and lossless output straight to the capture buffer (#1513, #1516,
    #1522), and Apple lossless 4:2:0 pictures on the scaler (#1520).
  - Display: a compact DP audio endpoint query sized for the catalog
    (#1523), which stops the J616s DCP crash on a gdm restart with an
    external display.
  - M4 Pro/Max: the T6040 DWI read-only view (#1512) and the read-only
    boot NOR firmware partition (#1514).
  - M5 Pro/Max (T6050): USB4 DisplayPort tunnels, display clocks and the
    J714s external displays (#1268, #1270, #1271, #1515), with host tests
    (#1524).
  - SEP, continued: one Touch ID match releases one key operation, with
    reply-wait, SCRD and ioctl hardening (#1541); disk-encryption secrets
    sealed to a user's key bag per OS install and unlockable from the
    initrd (#1339); sep-key interface 4 with keys under a user's key bag
    and the password checked by the enclave (#1544).
  - GPU: bounded large G17 pins can release clean page cache (#1526).
  - Wi-Fi: MT7932 probes asynchronously (#1545).
  - Boot log: three per-boot info/debug floods are quieter (hwmon thermal
    zones, DCP audio, asahi IO map; #1519).
- kernel-aurora-core conflicts with aurora-fido before 0.2.0-2, which
  does not speak sep-key interfaces 3 and 4 and crash-loops here.
- config and fedora.config are unchanged; olddefconfig adds
  CONFIG_APPLE_AURORA_BOOT_SECURITY=y and leaves the new
  CONFIG_APPLE_SEP_KEY_RESEARCH off. vmlinuz stays the raw Image, and the
  DT ABI generation stays 1.

* Wed Nov 11 2026 Ryan Murray <ryan@aurorasilicon.org> - 7.3.0-32
- Pin integration/aurora 451dc709 (linux#1507), 85 merges (645 commits)
  after 15f88e1c:
  - GPU: M5 GPU and firmware-27 display support (#1012) with its G17 and
    M5 fixes (#1503, #1504, #1508, #1229, #1177); lower host latency and
    CPU capacity hints for G13/G14 submission and syncobj waits (#1500,
    #1481); quiet teardown of a closing client (#1427); a single
    reservation lock in gpuvm exec (#1392); the M3 MacBook Air GPU runtime
    (CONFIG_DRM_ASAHI_M3_T8122, from asahi.config; #964).
  - SEP and Touch ID: the aurora-sep tool takes the distribution packages'
    changes (#1036); the SEP chardevs are published without holding their
    slot locks (#1449); the xART guard list is opened per access (#1264);
    unreadable identity state is kept (#962).
  - Media: AVE H.264 encode with B pictures on the M1 Pro and M2 6070
    firmware (#1387, #1440, #1484); media PMP performance requests from
    the boot loader (#1485); PMP performance for the M1 Pro scaler and
    ProRes (#1507).
  - ANE: H16 starts its firmware once the PMP runs and restarts a stopped
    startup at once (#1502, #1412); T8112 sets the firmware perf mode at
    power-on (#1450); an engine that a power cycle cannot restore stays
    wedged (#1446).
  - Display: the DP audio endpoint probes again when the EDID is not read
    yet (#1482); EDR switches on without a mode set (#1424); the loader's
    panel mode is adopted at takeover (#1439); the firmware-27 FORTIFY
    build fix (#1457); AFK endpoint initialisation (#1444).
  - M4 Pro/Max (T6041): J614c SD reader, keyboard backlight, front camera,
    SEP, boot NOR and NVRAM, PMP, cpuidle and GPU temperatures (#1465,
    #1464, #1463, #1461, #1458, #1459, #1453, #1447); CPU energy model and
    die zone (#1452); the J616c ISP (#1368); 40-core M4 Max GPU work and
    the 25G83 profile (#1442, #1373); the J616s AOP audio IOMMU (#1505);
    boot NOR supply (#1330).
  - M5 Pro/Max (T6050): J714s device trees (#1428-#1434), PMP (#1376), CPU
    capacities (#1399), CLPC floors (#1405), WFI idle (#1152), a root port
    the boot loader left down (#1182).
  - Power and sensors: SMC PMU rails on the J413 and T6000 (#1462, #1448,
    #1390), J413 CPU temperatures (#1371), the M2 Pro/Max CPU energy model
    (#932), charge hold with CHLS (#1474), no manufacture date on the J700
    (#1478), lid-open reports during sleep (#1160), PCIe power domains kept
    in s2idle (#1311).
  - Also: kdump crash kernels (#1200), experimental MT7932 AWDL (#1346,
    #1469; off by default), SPI HID reply checks and keyboard/trackpad
    wake (#842, #1347), T6040 ATC PHY hard recovery (#1350),
    thunderbolt-net across partner restarts (#1338), TIPD power-role swap
    settle (#1402), GL9755 SD power sequencing (#1327), Centauri sibling
    probing (#1421), J604 device tree and firmware fixes (#1329, #1389,
    #1367), and APIF removal (#1363).
- config and fedora.config are unchanged. olddefconfig resolves the one line
  asahi.config gained (CONFIG_DRM_ASAHI_M3_T8122=y).
- vmlinuz stays the raw Image, and the DT ABI generation stays 1.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 7.3.0-31
- Install the raw Image as vmlinuz again (back out the EFI zboot image of
  7.3.0-29). On a J700 the zboot image never reaches the kernel: GRUB
  loads it and the machine stays dark until the watchdog resets it. The
  raw Image of the same kernel boots normally there.

* Tue Nov 10 2026 Diljit Singh <hey@djdev.me> - 7.3.0-30
- Pin integration/aurora 15f88e1c (linux#1365), 54 merges after b1c9943b.
  It keeps the 120 Hz fix for ProMotion panels on M1 and M2 Macs
  (linux#1307), and adds: WPA3/SAE offload that keeps the requested CCMP
  cipher and AWDL join scans on the firmware's budgets (#1058, #1336);
  the J713 powering its display domains down while blanked (#1059); a GPU
  fence that never signals no longer wedging the display (#1241); G17
  recoveries that spare bystander clients and exiting clients that finish
  their work first (#1240, #1360); the M4 Max internal display on DCP
  (#1345); Thunderbolt XDomain and NHI fixes (#1319, #1150); GPU and CPU
  temperatures on M1 Pro/Max laptops, the J700 and the J413, and M1
  Pro/Max thermal zones (#1342, #1351, #1362); t600x PMU RTC wake alarms
  (#1312); Magic Mouse multitouch across sleep (#1317); SEP state
  reporting for aurora-sep status (#1335, #583); the MSR scaler driver
  (#1315); J704, J815, J604 and J773g device trees (#1231, #1361, #1186,
  #1181, #1187); and the T6050 (M5 Pro/Max) bare-metal series.
- The build now also resolves CONFIG_VIDEO_APPLE_SCALER, CONFIG_APPLE_DBGVIEW
  and CONFIG_APPLE_REGVIEW as modules, which asahi.config requests.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 7.3.0-29
- Install the EFI zboot image (CONFIG_EFI_ZBOOT, zstd) as vmlinuz instead
  of the raw Image: about 17 MB instead of 67 MB. GRUB reads the kernel
  through firmware block I/O, which costs about 30 ms per MB on a MacBook
  Pro M1 Pro: the boot loader stage takes 1.5 s less there. The kernel
  itself is the same; the EFI stub decompresses it.

* Mon Nov 09 2026 Diljit Singh <hey@djdev.me> - 7.3.0-28
- Pin integration/aurora b1c9943b. Fixes ProMotion internal displays that
  rendered at 60 Hz while set to 120 Hz on legacy DCP firmware (linux#1307).
- Drop 0001 and 0002. The driver now serves both speaker protection
  interfaces and boots every card on "Speaker Volume Unlock", the interface
  speakersafetyd uses (linux#1279); the MCA PCM bound is linux#1258.

* Mon Nov 09 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 7.3.0-27
- Fix speaker audio on M1 and M2 Macs: speakersafetyd could not open the
  speaker sense PCM (snd_pcm_hw_params -ENOMEM), restarted in a loop and
  never unlocked the speakers, so they stayed silent at the kernel's floor.
  Bound the MCA PCM buffer at 3 MiB again (linux 79af0bae4d0d had dropped the
  capture preallocation that used to bound it). Protection is unchanged.


* Sun Nov 08 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-26
- Restore the Asahi Speaker Volume Unlock interface for speakersafetyd and
  speakerguardd 0.1, retaining the -25 kernel and generation-1 device trees.
- Restore the matching J700 software-gain contract and legacy audio tests.
- Require the restored audio profiles for kernel-only updates.


* Sun Nov 08 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 7.3.0-25
- Track aurora-silicon/linux integration/aurora at d4d2678, the fleet32
  kernel tree. The packaged device trees for the M1 Pro, M2, M4 Pro and
  J700 then match the ones those Macs boot (integration 50d5865e and later;
  the DTS changes since then add T6050 boards only).
- Touch ID re-arm on finger lift, the macOS match policy and the password
  count reset (#1087, #1134, #1143), SEP host-store fixes (#1189, #1193),
  J700 speaker full scale (#1201), AVD dma-coherent and command parity
  (#1116, #1169), the J616s scaler (#1168), the M3 and M4 GPUs on by
  default (#1170, CONFIG_DRM_ASAHI_G15), NVMe, RTKit, dockchannel and SMC
  hwmon fixes (#1060, #1082, #1083, #1084), ADT coverage checks (#1111,
  #1172) and device trees for more M1 to M5 Macs, T6050 included.

* Sun Nov 08 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-24
- Track aurora-silicon/linux integration/aurora at 44bbfe1 for the CTXR
  follow-ups (#1079): /sys/kernel/execmem_confine/ reports the window and
  its pool, crashkernel= is skipped while a window is active, the device
  tree's window wins over a ctxr_exec_window= that doesn't match it, and an
  oops names the window when a kernel fetch outside it faults.
- Also device-tree syncs (#1029, #1030, #1034, #1086), the Stockholm NFC
  controller driver, which reads its identity and powers it off (#1042),
  a Touch ID lockout that a password re-arms (#904), the TAS2764 init
  quirks again after a resume that reset the amp (#1080), a brcmfmac
  flowring count fix (#1081), and G17 GPU submit and recovery changes
  (#1075, #1076).
- Device trees for every M1 to M4 Mac, including the J715 (#1129), the M4
  Pro and Max boards (#1140), the T8132 boards (#1142) and completeness and
  style passes (#1094, #1112, #1141, #1144); the J715 panel timing
  (#1161); M1 and M2 PMU RTC alarms (#1151); and AV1 tile checks, ANE and
  AVD fixes for T6041 and the J700 (#1088, #1091, #1100, #1137).

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 7.3.0-23
- Ship the DT ABI generation and require trial-aware Stage 2 updates.
- Clean boot files for every erased install-only kernel version.

* Sun Nov 08 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 7.3.0-22
- Defer the fbcon takeover, as Fedora's own kernel does. A quiet boot no
  longer shows a text cursor between the boot loader's logo and the splash.

* Sat Nov 07 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-21
- Provide aurora-ctxr-execmem. The 4731456 kernel is built with
  CONFIG_ARM64_CTXR_EXECMEM (#985), which an aura without the monitor
  requires.

* Sat Nov 07 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-20
- Track aurora-silicon/linux integration/aurora at 4731456. Wi-Fi works
  again on Macs with a BCM4378 (M1 MacBook Air, 13-inch M1 and M2 MacBook
  Pro): its receive buffers stay readable for the chip, as they already
  were for the BCM4387 and BCM4388 (#1078). Also SoC error reporting
  (EDAC), a PCIe link retry, the SMC RTC offset rounding fix, the AOP
  motion sensor trigger, and the speaker mux.

* Fri Nov 06 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-19
- Track aurora-silicon/linux integration/aurora at 9127278. M1 Macs no
  longer need apple_sep xart_guard=0 for Touch ID (#1049), an M1/M2 dock
  keeps its USB when its display has no pipeline (#1023), and every
  internal panel publishes an identity EDID (#1016). Also M4 MacBook Air
  camera, Touch ID and 4K 120 Hz external displays, M4 Pro JPEG engines,
  MacBook Air M5 NVMe, Wi-Fi, Bluetooth and GPU bring-up, the Mac mini M6
  GPU backend, and the Neo's eUSB2 repeater and USB hub tuned like macOS.

* Fri Nov 06 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 7.3.0-18
- Require aura 1.0.0~b5 or later. This kernel takes each SN012776 amp's
  level, brownout and DC blocker settings from the DT that aura 1.0.0b5
  fills in; with an older Stage 2 its speakers stay off. The dependency
  pulls in aura on a kernel-only upgrade, and update-m1n1 writes the new
  Stage 2 in the same transaction.

* Thu Nov 05 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-17
- Track aurora-silicon/linux integration/aurora at 2661d71: a T6020
  Thunderbolt-dock display that drops HPD while its CRTC stays on is
  power-cycled, so it comes back after wake or unblank (#959), and M1/M2
  panel backlight changes fade over 250 ms on DAC firmware (#983). Also
  M4 MacBook Air audio, suspend-to-idle, USB4 and external displays,
  T6041/J616c bring-up, display processors started concurrently, critical
  thermal trips confirmed over consecutive samples, and SN012776 amp setup
  from the ADT.

* Tue Nov 03 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-16
- Track aurora-silicon/linux integration/aurora at 21f7ffc (fleet15: the
  Neo DRAM floor while ProRes encodes, H16 ANE dynamic power gating held
  off across back-to-back requests, and the Apple KVM system registers
  kept in encoding order so KVM initialises). The configuration gains
  the Apple x86 flags, x86 FP, FP preserve and AMX options from the
  shared hardware fragment.

* Tue Nov 03 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-15
- Track aurora-silicon/linux integration/aurora at 40199ed.
- Upstream head: Merge pull request #898 from aurora-silicon/integration/rosetta-features
- Add aurora-userpages: the userpages launcher from this kernel source,
  required by kernel-aurora, and user4k=on on the kernel command line, so
  per-process 4K userspace pages work out of the box. user4k=off turns
  them off.

* Tue Nov 03 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-14
- Track aurora-silicon/linux integration/aurora at f153499 (fleet14p:
  the J614s device tree with its speakers off, H16 and H17 Neural Engine
  sleep, Neo AVE mailbox wake and ProRes/JPEG performance, the J616s
  thermal switch-on fix, brcmfmac suspend and escan fixes, T6041 PMGR
  banks, T6000 GFX resume wait, the late USB4 router and the DCP compact
  service re-announce, the boot NOR flash parts of the J616s and the
  J700 GigaDevice for NVRAM writes, the J616s ANE shared-memory stall
  fix, Neo GPU recovery that keeps other clients alive, whole-word T6000
  DCS commands, ALS colour temperature and the M2 Pro/Max second-install
  keybag).

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-13
- Track aurora-silicon/linux aurora-wip at 0652b3b: the Type-C ports take a
  USB4 router that binds after the deferred-probe timeout, keybag creation
  may rewrite its shared xART record (Touch ID on a second Linux install),
  NVRAM writes on the J616s and J700 boot NOR parts, the J614s M4 Pro
  MacBook Pro, H16/H17 Neural Engine sleep, the ambient-light colour
  temperature as in_colortemp_input, Wi-Fi suspend and scan fixes, and PMGR,
  AVE and DCP fixes.

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-12
- Track aurora-silicon/linux aurora-wip at e1524e6 (fleet14l: HEVC 10-bit
  decode, ProRes and JPEG encoders, the M4 Pro PMU RTC wake alarm and the
  H17 Neural Engine bind), promoted on all four Aurora Macs.

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-11
- Track aurora-silicon/linux aurora-wip at 52f0a6b (fleet14h: Neo AVD
  performance request, AV1 single-stream overlap, Neo H17 ANE disabled in
  the device tree, mt7932 directed scan), promoted on all four Aurora Macs.

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-10
- Track aurora-silicon/linux aurora-wip at b35adc7 (fleet14g: external
  VRR, panel EDR, H16 ANE cold boot, H14 ANE program lifetime, Neo encoder
  performance request, M2 SIO bring-up and H.264 fixes), promoted on all
  four Aurora Macs.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-9
- Track aurora-silicon/linux aurora-wip at f41ac3d (fleet14c, promoted on
  all four Aurora Macs). Release 8 was rebuilt from an older pin by mistake;
  this release supersedes it.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-8
- Track aurora-silicon/linux aurora-wip at 0529247 (fleet14, the kernel
  the Aurora Macs run), moving from integration/aurora 5d7c3e7.

* Sat Oct 31 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-7
- Use the source-pinned shared hardware fragment on every supported Mac.
- Retain Fedora peripheral policy in the distribution base; retire local hardware copies.
- Match shared dock, memory hotplug and diagnostics policy with Arch and NixOS.

* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-6
- Track aurora-silicon/linux integration/aurora at 5d7c3e7.
- Upstream head: Merge pull request #624 from aurora-silicon/ci/host-tests-integ

* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-5
- Track aurora-silicon/linux integration/aurora at 695d974.
- Upstream head: Merge pull request #575 from aurora-silicon/fix/t8140-j700-no-ave

* Wed Oct 28 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-4
- Track aurora-silicon/linux integration/aurora at d266c70.
- Upstream head: drm/asahi: g17: drop the completion thread's frequency boost while the GPU is the bottleneck

* Mon Oct 26 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-3
- Track aurora-silicon/linux integration/aurora at 9cbdd07.
- Upstream head: Merge pull request #423 from aurora-silicon/perf/g17-submit-completion-20261024

* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-2
- Track aurora-silicon/linux integration/aurora at 311471f.
- Upstream head: Merge pull request #402 from aurora-silicon/j616s/pmp-ep7-20261024

* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-1
- Move to Linux 7.3 from aurora-silicon/linux integration/aurora at 8c2774e.
- Keep the CIO reset controller built in so it exists before the USB4 routers probe.
- Add bounded acceleration-structure build execution for the Aurora Mesa.
- Carry the G17 scheduler and queue stability fixes for MacBook Neo graphics.
- Select the MT7932 country regulatory package with a world fallback.
- Carry Apple SMC, pinctrl, Type-C, DMA, Bluetooth and Wi-Fi fixes from the M4 Pro work.

* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 7.2.10-7
- Track integration/aurora at 70d5dce.
- Build the Apple watchdog driver in, fixing early resets on MacBook Neo first boot.
- Fix very dim internal panels at first boot on Macs with 13.x system firmware.
- Add MT7932 WPA3-SAE and OWE station offload and a world regulatory fallback.

* Tue Oct 20 2026 Aurora Silicon <hey@djdev.me> - 7.2.10-6
- Track integration/aurora with its shared Asahi hardware configuration.
- Use the upstream M4+ wait-state implementation.

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 7.2.10-5
- Keep integrated audio, camera, haptics and USB4 capabilities enabled.
- Include common PCIe network, storage, audio and external GPU drivers.

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 7.2.10-4
- Enable SELinux for Fedora targeted policy on every supported Mac.
- Reject requested platform capabilities silently dropped by Kconfig.

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 7.2.10-3
- Include the MAX98360A codec needed to bind MacBook Neo audio.

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 7.2.10-2
- Carry the merged Apple M4+ wait-state fix without requiring boot flags.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 7.2.10-1
- Initial Fedora Aurora package.
