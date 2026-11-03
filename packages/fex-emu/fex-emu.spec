# FEX from Aurora's fork, under Fedora's fex-emu package names so it replaces
# Fedora's build, plus `fex` so that `dnf install fex` gets it too (Fedora's
# own `fex` is an unrelated field-extraction tool). Derived from Fedora's
# fex-emu.spec (f44, FEX 2604); the sysroot, its macros and the toolchain files
# are Fedora's. The fork's submodules are pinned as extra sources in
# sources.json at the gitlinks of %%{commit}.
%global commit 3f4ee4277f11b1986a5edf8ecc9c2c4169830bd4
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global fex_describe FEX-%{version}-aurora-g%{shortcommit}

# FEX upstream only supports building with clang
%global toolchain clang

%global has_sysroot 1
%bcond thunks 1
# The x86 tests need an x86 cross toolchain and are not run here.
%bcond check 0

Name:       fex-emu
Version:    2610
Release:    1%{?dist}.aurora
Summary:    Fast usermode x86 and x86-64 emulator for ARM64

# FEX itself is MIT, see below for the bundled libraries
%global fex_license MIT AND Apache-2.0 AND BSL-1.0 AND BSD-3-Clause AND GPL-2.0-only
License:    %{fex_license}
URL:        https://github.com/aurora-silicon/fex
Source0:    fex-emu-%{commit}.tar.gz
Source1:    README.aurora
# The sysroot is Fedora's (build-fex-sysroot.sh downloads Fedora's x86_64 RPMs
# and repacks them). Its version and license expression are Fedora's
# fex-sysroot-macros.inc, inlined so that dnf builddep can parse this spec.
%global sysroot_version fc44-20260410
%global sysroot_license ( ((GPL-2.0-only WITH Linux-syscall-note) OR BSD-2-Clause) AND ((GPL-2.0-only WITH Linux-syscall-note) OR BSD-3-Clause) AND ((GPL-2.0-only WITH Linux-syscall-note) OR CDDL-1.0) AND ((GPL-2.0-only WITH Linux-syscall-note) OR Linux-OpenIB) AND ((GPL-2.0-only WITH Linux-syscall-note) OR MIT) AND ((GPL-2.0-or-later WITH Linux-syscall-note) OR BSD-3-Clause) AND ((GPL-2.0-or-later WITH Linux-syscall-note) OR MIT) AND BSD-3-Clause AND (GPL-1.0-or-later WITH Linux-syscall-note) AND GPL-2.0-only AND (GPL-2.0-only WITH Linux-syscall-note) AND (GPL-2.0-or-later WITH Linux-syscall-note) AND (LGPL-2.0-or-later WITH Linux-syscall-note) AND (LGPL-2.1-only WITH Linux-syscall-note) AND (LGPL-2.1-or-later WITH Linux-syscall-note) AND MIT ) AND( GPL-3.0-or-later AND LGPL-3.0-or-later AND (GPL-3.0-or-later WITH GCC-exception-3.1) AND (GPL-3.0-or-later WITH Texinfo-exception) AND (LGPL-2.1-or-later WITH GCC-exception-2.0) AND (GPL-2.0-or-later WITH GCC-exception-2.0) AND (GPL-2.0-or-later WITH GNU-compiler-exception) AND BSL-1.0 AND GFDL-1.3-or-later AND Linux-man-pages-copyleft-2-para AND SunPro AND BSD-1-Clause AND BSD-2-Clause AND BSD-2-Clause-Views AND BSD-3-Clause AND BSD-4-Clause AND BSD-Source-Code AND Zlib AND MIT AND Apache-2.0 AND (Apache-2.0 WITH LLVM-Exception) AND ZPL-2.1 AND ISC AND LicenseRef-Fedora-Public-Domain AND HP-1986 AND curl AND Martin-Birgmeier AND HPND-Markus-Kuhn AND dtoa AND SMLNJ AND AMD-newlib AND OAR AND HPND-merchantability-variant AND HPND-Intel ) AND( LGPL-2.1-or-later AND SunPro AND LGPL-2.1-or-later WITH GCC-exception-2.0 AND BSD-3-Clause AND GPL-2.0-or-later AND LGPL-2.1-or-later WITH GNU-compiler-exception AND GPL-2.0-only AND ISC AND LicenseRef-Fedora-Public-Domain AND HPND AND CMU-Mach AND LGPL-2.0-or-later AND Unicode-3.0 AND GFDL-1.1-or-later AND GPL-1.0-or-later AND FSFUL AND MIT AND Inner-Net-2.0 AND X11 AND GPL-2.0-or-later WITH GCC-exception-2.0 AND GFDL-1.3-only AND GFDL-1.1-only AND GPL-3.0-or-later AND GPL-3.0-or-later WITH Autoconf-exception-generic-3.0 AND GPL-3.0-or-later WITH Texinfo-exception )
Source3:    fex-sysroot-%{sysroot_version}.tar.gz
Source4:    toolchain_x86_32.cmake
Source5:    toolchain_x86_64.cmake
Source6:    build-fex-sysroot.sh
SourceLicense: %{fex_license} %{sysroot_license}

# Bundled dependencies are git submodules upstream; each is pinned in
# sources.json (extra_sources) at the fork's gitlink.
Source101:  cpp-optparse-9f94388a339fcbb0bc95c17768eb786c85988f6e.tar.gz
Source102:  drm-headers-3e49836995c1dcb3df709440ad2f270b569c6a5f.tar.gz
Source103:  jemalloc-8436195ad5e1bc347d9b39743af3d29abee59f06.tar.gz
Source104:  range-v3-ca1388fb9da8e69314dda222dc7b139ca84e092f.tar.gz
Source105:  rpmalloc-09142d726429416bfa7b459151515fe3ab7622dd.tar.gz
Source106:  Vulkan-Headers-ee2ec5fd83dafce291024683b50dc89219333076.tar.gz
Source107:  vixl-585d860b12cdfc3a72f5fdad5e02e4d50a64c014.tar.gz
Source108:  unordered_dense-3234af2c03549bc85656bfd3a86993bf1cd8aef1.tar.gz
Provides:   bundled(cpp-optparse) = 0
Provides:   bundled(kernel) = 6.17
Provides:   bundled(jemalloc) = 5.3.0
Provides:   bundled(range-v3) = 0.12.0
Provides:   bundled(rpmalloc) = 1.3.0
Provides:   bundled(vulkan-headers) = 1.4.337
Provides:   bundled(vixl) = 0
Provides:   bundled(unordered_dense) = 0

ExclusiveArch:  aarch64

BuildRequires:  cmake
BuildRequires:  clang
BuildRequires:  git-core
BuildRequires:  lld
BuildRequires:  llvm
BuildRequires:  ninja-build
BuildRequires:  python3
BuildRequires:  python3-setuptools
BuildRequires:  sed
BuildRequires:  systemd-rpm-macros
BuildRequires:  catch-devel
BuildRequires:  fmt-devel
BuildRequires:  libepoxy-devel
BuildRequires:  SDL2-devel
BuildRequires:  xxhash-devel
%if %{with thunks}
BuildRequires:  alsa-lib-devel
BuildRequires:  clang-devel
BuildRequires:  libdrm-devel
BuildRequires:  libglvnd-devel
BuildRequires:  libX11-devel
BuildRequires:  libXrandr-devel
BuildRequires:  llvm-devel
BuildRequires:  openssl-devel
BuildRequires:  wayland-devel
BuildRequires:  zlib-devel
%endif
BuildRequires:  cmake(Qt6Qml)
BuildRequires:  cmake(Qt6Quick)
BuildRequires:  cmake(Qt6Widgets)

Requires:       systemd-udev
Requires:       %{name}-filesystem = %{version}-%{release}
%if %{with thunks}
Recommends:     %{name}-thunks = %{version}-%{release}
%endif
# 4 KiB page process trees on Aurora's 16 KiB kernels.
Recommends:     aurora-userpages
Recommends:     fex-emu-rootfs-fedora
Recommends:     erofs-fuse
Recommends:     erofs-utils
Recommends:     squashfs-tools
Recommends:     squashfuse

Obsoletes:      fex-emu-gdb < 2409-4
Provides:       fex-emu-gdb = %{version}-%{release}

# Do not check guest thunks for requires, since these are x86-64 binaries that link against libs in the FEX RootFS.
%global __requires_exclude_from ^%{_datadir}/fex-emu/GuestThunks.*$
# Do not check guest and host thunks for provides, since these are not general system libraries on the host.
%global __provides_exclude_from ^(%{_datadir}/fex-emu/GuestThunks.*|%{_libdir}/fex-emu/HostThunks.*)$

%description
FEX runs x86 and x86-64 Linux programs on an AArch64 host. This build comes
from Aurora's fork. It uses the hardware TSO memory model when the kernel
offers it, and runs in the 4 KiB page process trees that Aurora kernels
provide (see README.aurora).

%package     -n fex
Summary:        FEX x86 and x86-64 emulator (Aurora build)
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description -n fex
Installs FEX, the x86 and x86-64 emulator, from Aurora's fork (fex-emu). The
`fex` name lets `dnf install fex` find the emulator; it does not ship
Fedora's unrelated `fex` field-extraction tool.

%package        filesystem
Summary:        FEX rootfs and overlay filesystem
BuildArch:      noarch

%description    filesystem
%{summary}.

%package        devel
Summary:        Development headers and libraries for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
This package provides development headers and libraries for %{name}.

%package        utils
Summary:        Utility tools for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    utils
This package provides utility tools for %{name} for advanced users.

%if %{with thunks}
%package        thunks
Summary:        Thunk libraries for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    thunks
This package provides host library thunks for %{name}.
%endif

%prep
%autosetup -N -n fex-%{commit}
cp -p %SOURCE1 .
unpack() { mkdir -p "$2"; tar -xzf "$1" --strip-components=1 -C "$2"; }
unpack %{SOURCE101} Source/Common/cpp-optparse
unpack %{SOURCE102} External/drm-headers
unpack %{SOURCE103} External/jemalloc_glibc
unpack %{SOURCE104} External/range-v3
unpack %{SOURCE105} External/rpmalloc
unpack %{SOURCE106} External/Vulkan-Headers
unpack %{SOURCE107} External/vixl
unpack %{SOURCE108} External/unordered_dense

# Ensure library soversion is set
sed -i FEXCore/Source/CMakeLists.txt \
  -e '/PROPERTIES OUTPUT_NAME/aset_target_properties(${Name} PROPERTIES VERSION %{version})'

tar xzf %SOURCE3
cp -p %SOURCE4 %SOURCE5 .
CPPINC="/$(cd sysroot; ls -d usr/include/c++/*)"
sed -i "s,%%CPPINC%%,$CPPINC,g" toolchain_*.cmake

%build
# FEX tunes for the build machine by default (-mcpu from its /proc/cpuinfo),
# which crashes with SIGILL on Apple CPUs when CI builds on Neoverse.
%cmake -G Ninja \
    -DCMAKE_BUILD_TYPE=release \
    -DENABLE_OFFLINE_TELEMETRY=OFF \
    -DENABLE_CCACHE=OFF \
    -DTUNE_CPU=none \
    -DOVERRIDE_VERSION=%{fex_describe} \
    -DOVERRIDE_HASH=%{commit} \
%if %{with thunks}
    -DBUILD_THUNKS=ON \
    -DENABLE_CLANG_THUNKS=ON \
%endif
    -DBUILD_TESTING=OFF \
    -DBUILD_FEX_LINUX_TESTS=OFF \
    -DX86_DEV_ROOTFS=$PWD/sysroot \
    -DX86_32_TOOLCHAIN_FILE=$PWD/toolchain_x86_32.cmake \
    -DX86_64_TOOLCHAIN_FILE=$PWD/toolchain_x86_64.cmake \
    %{nil}
%cmake_build

%install
%cmake_install
# These are used to store RootFS and overlays for FEX that will be provided
# by other packages
install -Ddpm0755 %{buildroot}%{_datadir}/fex-emu/RootFS/
install -Ddpm0755 %{buildroot}%{_datadir}/fex-emu/overlays/
%if !%{with thunks}
rm %{buildroot}%{_datadir}/fex-emu/ThunksDB.json
%endif

%check
# The installed tools report the fork's identity.
LD_LIBRARY_PATH=%{buildroot}%{_libdir} %{buildroot}%{_bindir}/FEXGetConfig --version | tee version.txt
grep -qx '%{fex_describe}' version.txt
for f in %{buildroot}%{_binfmtdir}/FEX-x86.conf %{buildroot}%{_binfmtdir}/FEX-x86_64.conf; do
  grep -q ':%{_bindir}/FEX:' "$f"
done

%postun
if [ $1 -eq 0 ]; then
/bin/systemctl try-restart systemd-binfmt.service
fi

%files
%license LICENSE
%doc Readme.md README.aurora docs
%{_bindir}/FEX
%{_bindir}/FEXBash
%{_bindir}/FEXGetConfig
%{_bindir}/FEXOfflineCompiler
%{_bindir}/FEXpidof
%{_bindir}/FEXServer
%{_libdir}/libFEXCore.so.%{version}
%{_binfmtdir}/FEX-x86.conf
%{_binfmtdir}/FEX-x86_64.conf
%{_datadir}/fex-emu/AppConfig/
%{_mandir}/man1/FEX.1*

%files -n fex
%doc README.aurora

%files filesystem
%dir %{_datadir}/fex-emu/
%dir %{_datadir}/fex-emu/RootFS
%dir %{_datadir}/fex-emu/overlays

%files devel
%{_includedir}/FEXCore/
%{_libdir}/libFEXCore.so

%files utils
%{_bindir}/FEXConfig
%{_bindir}/FEXRootFSFetcher

%if %{with thunks}
%files thunks
%{_libdir}/fex-emu/HostThunks/
%{_libdir}/fex-emu/HostThunks_32/
%{_datadir}/fex-emu/ThunksDB.json
%{_datadir}/fex-emu/GuestThunks/
%{_datadir}/fex-emu/GuestThunks_32/
%endif

%changelog
* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 2610-1.aurora
- FEX from aurora-silicon/fex main at 3f4ee42 (FEX-2610 and 19 commits:
  io_uring for x86-64 guests behind ring restrictions, one compile per
  guest entry when threads miss on it together, multiblock stops at padding
  after a call), replacing Fedora's fex-emu 2604.
- Ship `fex` so that `dnf install fex` installs the emulator.
