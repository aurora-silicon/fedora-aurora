%global commit e0fa50d863ee7747de0af16525dfd974cdd826f8
%global krel %{version}-%{release}.aarch64
%global debug_package %{nil}
Name: kernel-aurora
Version: 7.2.10
Release: 2%{?dist}.aurora
Summary: Aurora kernel for Apple Silicon Macs
License: GPL-2.0-only
URL: https://github.com/aurora-silicon/linux
Source0: kernel-aurora-%{commit}.tar.gz
Source1: config
Source2: common.config
Source3: neo.config
# Merged upstream in omacom/linux-aurora#147; also needed by this 7.2 source pin.
Patch0: 0001-arm64-apple-m4-wait-state.patch
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
scripts/kconfig/merge_config.sh -m .config %{SOURCE2} %{SOURCE3}
scripts/config --set-str LOCALVERSION '' --disable LOCALVERSION_AUTO --set-str SYSTEM_TRUSTED_KEYS '' --set-str SYSTEM_REVOCATION_KEYS ''

%build
export ARCH=arm64 RUSTC_BOOTSTRAP=1
export RUST_LIB_SRC=/usr/lib/rustlib/src/rust/library
# Build the pinned, corrected generator. It independently compiles its fixtures.
python3 tools/aurora-bindgen/build.py --output-dir "$PWD/private-bindgen"
export BINDGEN="$PWD/private-bindgen/rust-bindgen-0.73.2/target/release/bindgen"
make LLVM=1 LOCALVERSION=-%{release}.aarch64 BINDGEN="$BINDGEN" olddefconfig
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
* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 7.2.10-2
- Carry the merged Apple M4+ wait-state fix without requiring boot flags.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 7.2.10-1
- Initial Fedora Aurora package.
