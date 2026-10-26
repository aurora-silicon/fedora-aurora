%global commit 916dcbf7d546f21eb8059d84a21ce5530fb79194
%global krel %{version}-%{release}.aarch64
%global debug_package %{nil}
Name: kernel-aurora
Version: 7.3.0
Release: 3%{?dist}.aurora
Summary: Aurora kernel for Apple Silicon Macs
License: GPL-2.0-only
URL: https://github.com/aurora-silicon/linux
Source0: kernel-aurora-%{commit}.tar.gz
Source1: config
Source2: common.config
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
scripts/kconfig/merge_config.sh -m .config arch/arm64/configs/asahi.config %{SOURCE2} %{SOURCE4}
scripts/config --set-str LOCALVERSION '' --disable LOCALVERSION_AUTO --set-str SYSTEM_TRUSTED_KEYS '' --set-str SYSTEM_REVOCATION_KEYS ''

%build
export ARCH=arm64 RUSTC_BOOTSTRAP=1
export RUST_LIB_SRC=/usr/lib/rustlib/src/rust/library
# Build the pinned, corrected generator. It independently compiles its fixtures.
python3 tools/aurora-bindgen/build.py --output-dir "$PWD/private-bindgen"
export BINDGEN="$PWD/private-bindgen/rust-bindgen-0.73.2/target/release/bindgen"
make LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" olddefconfig
python3 %{SOURCE5} arch/arm64/configs/asahi.config %{SOURCE2} %{SOURCE4} .config
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
* Mon Oct 26 2026 Ryan Murray <ryan@aurorasilicon.org> - 7.3.0-3.aurora
- Use the consistency kernel and its shared hardware fragment.
- Retire the duplicate Neo fragment and validate ordered shared requirements.

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
