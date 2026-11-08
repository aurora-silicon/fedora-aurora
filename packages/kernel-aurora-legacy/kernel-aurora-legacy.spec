%global commit f92b6bc6b736b19921e9f2df91ed8846ab5cd05e
%global krel %{version}-%{release}.aarch64
%global debug_package %{nil}
# 1 with a kernel pin whose configuration resolves CONFIG_ARM64_CTXR_EXECMEM=y
# (aurora-silicon/linux#985), which keeps every kernel code page inside the CTXR
# window an aura without the monitor moves the kernel into. kernel-aurora-legacy-core
# then provides aurora-ctxr-execmem, which that aura requires. %%build checks it.
%global ctxr_execmem 0
Name: kernel-aurora-legacy
Version: 7.3.0
Release: 1%{?dist}.aurora.legacy
Summary: Optional legacy-speaker recovery kernel for the M2 MacBook Pro J493
License: GPL-2.0-only
URL: https://github.com/aurora-silicon/linux
Source0: kernel-aurora-legacy-%{commit}.tar.gz
Source1: config
Source4: fedora.config
Source5: validate-config.py
Source6: dtb-abi
Source7: README.md
ExclusiveArch: aarch64
BuildRequires: make gcc gcc-c++ clang llvm lld rust rust-src rustfmt cargo bindgen-cli
BuildRequires: bc bison flex dtc openssl-devel elfutils-libelf-devel dwarves cpio perl python3 patch
Requires: kernel-aurora-legacy-core = %{version}-%{release}
Requires: kernel-aurora-legacy-modules-extra = %{version}-%{release}
# Not versioned: older installed kernels must not hold back its updates.
Requires: aurora-userpages
Provides: installonlypkg(kernel)

%description
Opt-in recovery kernel for the 13-inch M2 MacBook Pro (J493), retaining the
legacy Asahi speakersafetyd interface and the BCM4378 receive-DMA fix.
It uses the generation-0 device trees of the -19/-20 kernel series and
installs beside kernel-aurora. This is not a replacement fleet kernel.

%package core
Summary: Aurora kernel image and device trees
Requires: coreutils kmod dracut grubby update-m1n1
Requires: speakersafetyd aurora-audio
# -25 introduced generation-1 DTBs; this recovery kernel uses generation 0.
Conflicts: kernel-aurora-core >= 7.3.0-25
# SN012776 amp settings come from the DT that aura 1.0.0b5 fills in
# (https://github.com/aurora-silicon/linux/pull/981,
# https://github.com/aurora-silicon/aura/pull/75); under an older Stage 2
# the speakers stay off.
Requires: aura >= 1.0.0~b5
Provides: kernel-uname-r = %{krel}
%if %{ctxr_execmem}
Provides: aurora-ctxr-execmem
%endif
Provides: installonlypkg(kernel)

%description core
Aurora kernel image and device trees for Fedora's kernel-install boot pipeline.

%package modules-extra
Summary: Matching Aurora kernel modules
Requires: kernel-aurora-legacy-core = %{version}-%{release}
Provides: kernel-modules-uname-r = %{krel}
Provides: installonlypkg(kernel)

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
ctxr=0
if grep -qx 'CONFIG_ARM64_CTXR_EXECMEM=y' .config; then ctxr=1; fi
if [ "$ctxr" != %{ctxr_execmem} ]; then
  echo "kernel-aurora-legacy.spec: set ctxr_execmem to $ctxr, which this pin's configuration resolves to" >&2
  exit 1
fi
make LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" rustavailable
make LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" %{?_smp_mflags} Image modules dtbs
[ "$(make -s LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" kernelrelease)" = "%{krel}" ]

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

%pre core
# This historical tree is a narrowly scoped recovery for the J493 report.
if ! tr '\000' '\n' < /sys/firmware/devicetree/base/compatible 2>/dev/null | grep -qx 'apple,j493'; then
  echo 'This legacy recovery kernel is only for Apple J493 (13-inch M2 MacBook Pro).' >&2
  exit 1
fi

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
%doc %{SOURCE7}

%files core -f metadata.files
%dir /usr/lib/modules/%{krel}
/usr/lib/modules/%{krel}/vmlinuz
/usr/lib/modules/%{krel}/config
/usr/lib/modules/%{krel}/System.map
/usr/lib/modules/%{krel}/dtb-abi
/usr/lib/modules/%{krel}/dtb/

%files modules-extra -f modules.files
%dir /usr/lib/modules/%{krel}/kernel

%changelog
* Sun Nov 08 2026 Aurora Silicon <hey@djdev.me> - 7.3.0-1
- Add an optional J493 recovery kernel from the legacy -19 source plus
  the BCM4378 receive-DMA fix (linux#1078), retaining speakersafetyd.
- Use a distinct package/module identity, preserve the installed -20 kernel,
  and refuse installs beside generation-1 (-25 and later) kernel trees.
