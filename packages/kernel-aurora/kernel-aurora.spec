%global commit f1534999589662d5a0fd84b8a4b2b0f886661930
%global krel %{version}-%{release}.aarch64
%global debug_package %{nil}
Name: kernel-aurora
Version: 7.3.0
Release: 14%{?dist}.aurora
Summary: Aurora kernel for Apple Silicon Macs
License: GPL-2.0-only
URL: https://github.com/aurora-silicon/linux
Source0: kernel-aurora-%{commit}.tar.gz
Source1: config
Source4: fedora.config
Source5: validate-config.py
ExclusiveArch: aarch64
BuildRequires: make gcc gcc-c++ clang llvm lld rust rust-src rustfmt cargo bindgen-cli
BuildRequires: bc bison flex dtc openssl-devel elfutils-libelf-devel dwarves cpio perl python3 patch
Requires: kernel-aurora-core = %{version}-%{release}
Requires: kernel-aurora-modules-extra = %{version}-%{release}
Provides: kernel-16k = %{version}-%{release}
Provides: installonlypkg(kernel)

%description
The Aurora kernel source and shared configuration for supported Apple Silicon
Macs, including MacBook Neo. Matching DTBs and modules are built together.

%package core
Summary: Aurora kernel image and device trees
Requires: coreutils kmod dracut grubby update-m1n1 aura
Provides: kernel-uname-r = %{krel}
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
make LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" rustavailable
make LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" %{?_smp_mflags} Image modules dtbs
[ "$(make -s LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" kernelrelease)" = "%{krel}" ]

%install
export ARCH=arm64 RUSTC_BOOTSTRAP=1
make LLVM=1 LOCALVERSION=-%{release}.aarch64 INSTALL_MOD_PATH=%{buildroot}/usr INSTALL_MOD_STRIP=1 modules_install
install -Dm644 arch/arm64/boot/Image %{buildroot}/usr/lib/modules/%{krel}/vmlinuz
install -m644 .config %{buildroot}/usr/lib/modules/%{krel}/config
install -m644 System.map %{buildroot}/usr/lib/modules/%{krel}/System.map
mkdir -p %{buildroot}/usr/lib/modules/%{krel}/dtb/apple
cp arch/arm64/boot/dts/apple/*.dtb %{buildroot}/usr/lib/modules/%{krel}/dtb/apple/
rm -f %{buildroot}/usr/lib/modules/%{krel}/build %{buildroot}/usr/lib/modules/%{krel}/source
find %{buildroot}/usr/lib/modules/%{krel} -type f -name '*.ko' > modules.files
sed -i 's@%{buildroot}@@' modules.files
find %{buildroot}/usr/lib/modules/%{krel} -maxdepth 1 -type f ! -name vmlinuz ! -name config ! -name System.map >> metadata.files
sed -i 's@%{buildroot}@@' metadata.files

%posttrans core
if [ -x /usr/bin/kernel-install ]; then
  /usr/bin/kernel-install add %{krel} /usr/lib/modules/%{krel}/vmlinuz || exit 1
fi

%preun core
if [ "$1" = 0 ] && [ -x /usr/bin/kernel-install ]; then
  /usr/bin/kernel-install remove %{krel} || :
fi

%files
%license COPYING

%files core -f metadata.files
%dir /usr/lib/modules/%{krel}
/usr/lib/modules/%{krel}/vmlinuz
/usr/lib/modules/%{krel}/config
/usr/lib/modules/%{krel}/System.map
/usr/lib/modules/%{krel}/dtb/

%files modules-extra -f modules.files
%dir /usr/lib/modules/%{krel}/kernel

%changelog
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
