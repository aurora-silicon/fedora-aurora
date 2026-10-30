# aurora-builder: x86_64
# x86_64 and i686 builds of the Aurora Mesa for x86 programs run by FEX.
# Keep commit, Version and Release identical to packages/mesa-aurora (and to
# sources.json): the guest driver must match the host driver and the kernel
# UAPI it speaks. tests/test_specs.py checks this.
#
# A host Mesa built from another recipe can be matched instead, without editing
# this file, e.g. for Fedora's mesa.spec line:
#   rpmbuild --define 'commit <40-hex>' --define 'host_version 26.3.0~devel' \
#            --define 'host_release 0.12.aurora.borealis.<12-hex>%%{?dist}' ...
# Both lines provide mesa-dri-drivers and mesa-vulkan-drivers at their own
# version-release, which is what this package requires.
%{!?commit:%global commit cf4e08105dfa526b8874318b6a52b3ce948f6297}
%{!?host_version:%global host_version 26.3.0}
%{!?host_release:%global host_release 10%{?dist}.aurora}
%global debug_package %{nil}
# Fedora's x86_64 build flags carry -m64 and would turn the i686 build into a
# second x86_64 one; meson's release buildtype sets the optimisation instead.
%undefine _auto_set_build_flags
%global __strip /bin/true
%global __brp_strip %{nil}
%global __brp_strip_static_archive %{nil}
%global __brp_strip_comment_note %{nil}
%global __brp_strip_lto %{nil}
%global _binaries_in_noarch_packages_terminate_build 0
%global __requires_exclude_from ^/usr/share/guestos/
%global __provides_exclude_from ^/usr/share/guestos/
%global layer /usr/share/guestos/aurora-fex-mesa-layer
Name: mesa-aurora-fex-guest
Version: %{host_version}
Release: %{host_release}
Summary: Aurora Mesa (x86_64 and i686) as the FEX guest graphics provider
License: MIT
URL: https://github.com/aurora-silicon/mesa
Source0: mesa-aurora-fex-guest-%{commit}.tar.gz
Source1: aurora-fex-mesa.service
Source2: 80-aurora-fex-mesa.preset
# The payload is x86 code for an aarch64 host: it is built on an x86_64 builder
# (Fedora multilib for i686) and shipped as noarch with automatic dependencies off.
#
# The drivers link neither LLVM nor SPIRV-Tools, as in mesa-aurora. They load
# inside the guest rootfs, whose LLVM is whatever its Fedora release ships (the
# Neo's carries LLVM 23, Fedora 44 builds against LLVM 22): a driver linked to
# the builder's libLLVM.so.N fails to load there, leaving the game without a GPU
# driver. lm_sensors and libunwind are off for the same reason. LLVM is needed
# only to precompile the CL shaders, so a first native build makes those
# compilers and both driver builds use them; no i686 LLVM, clang or translator.
BuildArch: noarch
AutoReqProv: no
Requires: mesa-dri-drivers = %{version}-%{release}
Requires: mesa-vulkan-drivers = %{version}-%{release}
Requires: util-linux-core
BuildRequires: gcc gcc-c++ meson ninja-build pkgconf-pkg-config bison flex glslang libclc
BuildRequires: python3-mako python3-pyyaml python3-packaging python3-pycparser python3-ply
BuildRequires: spirv-headers-devel wayland-protocols-devel systemd-rpm-macros file
BuildRequires: llvm-devel(x86-64) clang-devel(x86-64)
BuildRequires: spirv-llvm-translator-devel(x86-64) spirv-tools-devel(x86-64)
BuildRequires: libdrm-devel(x86-64) libdrm-devel(x86-32)
BuildRequires: wayland-devel(x86-64) wayland-devel(x86-32)
BuildRequires: libX11-devel(x86-64) libX11-devel(x86-32)
BuildRequires: libXext-devel(x86-64) libXext-devel(x86-32)
BuildRequires: libXfixes-devel(x86-64) libXfixes-devel(x86-32)
BuildRequires: libXxf86vm-devel(x86-64) libXxf86vm-devel(x86-32)
BuildRequires: libXrandr-devel(x86-64) libXrandr-devel(x86-32)
BuildRequires: libxcb-devel(x86-64) libxcb-devel(x86-32)
BuildRequires: libxshmfence-devel(x86-64) libxshmfence-devel(x86-32)
BuildRequires: libXdamage-devel(x86-64) libXdamage-devel(x86-32)
BuildRequires: zlib-ng-compat-devel(x86-64) zlib-ng-compat-devel(x86-32)
BuildRequires: libzstd-devel(x86-64) libzstd-devel(x86-32)
BuildRequires: expat-devel(x86-64) expat-devel(x86-32)
BuildRequires: elfutils-libelf-devel(x86-64) elfutils-libelf-devel(x86-32)
BuildRequires: libglvnd-devel(x86-64) libglvnd-devel(x86-32)
BuildRequires: libdisplay-info-devel(x86-64) libdisplay-info-devel(x86-32)
BuildRequires: vulkan-loader-devel(x86-64) vulkan-loader-devel(x86-32)
BuildRequires: glibc-devel(x86-64) glibc-devel(x86-32) libstdc++-devel(x86-64) libstdc++-devel(x86-32)
BuildRequires: libgcc(x86-32) libatomic(x86-64) libatomic(x86-32)
# Indirect pkg-config requirements (wayland, llvm, xcb, libdrm), named per arch:
# an unqualified pkgconfig() requirement may be satisfied by the i686 copy alone.
BuildRequires: libffi-devel(x86-64) libffi-devel(x86-32)
BuildRequires: libedit-devel(x86-64) ncurses-devel(x86-64)
BuildRequires: libxcrypt-devel(x86-64) libxcrypt-devel(x86-32)
BuildRequires: libXau-devel(x86-64) libXau-devel(x86-32)
BuildRequires: libXrender-devel(x86-64) libXrender-devel(x86-32)
BuildRequires: libpciaccess-devel(x86-64) libpciaccess-devel(x86-32)

%description
x86_64 and i686 builds of Aurora's Asahi Gallium, Zink and Honeykrisp drivers,
laid over the stock FEX guest rootfs as a Steam graphics provider at
/usr/share/guestos/aurora-fex-mesa. Without it, x86 games run under FEX load a
guest Mesa with no Apple G17P support and every GPU job they submit is rejected.

%prep
[ "$(uname -m)" = x86_64 ] || { echo 'mesa-aurora-fex-guest must be built on x86_64 (it ships x86 code)' >&2; exit 1; }
%autosetup -n mesa-%{commit}

%build
# rpm points PKG_CONFIG_PATH at the noarch %%{_libdir} (/usr/lib), which holds the
# i686 .pc files; each build below selects its own pkg-config directories.
unset PKG_CONFIG_PATH
export MESA_GIT_SHA1_OVERRIDE=%{commit}
common=(--prefix=/usr --buildtype=release -Db_ndebug=true --wrap-mode=nodownload
  -Dplatforms=x11,wayland -Dgallium-drivers=asahi,zink,softpipe -Dvulkan-drivers=asahi
  -Dvulkan-layers= -Dglx=dri -Degl=enabled -Dgbm=enabled -Dgles1=disabled -Dgles2=enabled -Dopengl=true
  -Dglvnd=enabled -Dgallium-rusticl=false -Dtools= -Dbuild-tests=false
  -Dvalgrind=disabled -Dvideo-codecs= -Dmicrosoft-clc=disabled -Dlibunwind=disabled -Dlmsensors=disabled)
drivers=(-Dllvm=disabled -Dspirv-tools=disabled -Dmesa-clc=system -Dprecomp-compiler=system
  --native-file tools.ini)
# The CL compilers run on the build machine and need LLVM.
PKG_CONFIG_LIBDIR=/usr/lib64/pkgconfig:/usr/share/pkgconfig meson setup tools "${common[@]}" --libdir=lib64 -Dllvm=enabled
ninja -C tools %{?_smp_mflags} src/compiler/clc/mesa_clc src/compiler/spirv/vtn_bindgen2 src/asahi/clc/asahi_clc
cat > tools.ini <<X
[binaries]
mesa_clc = '$PWD/tools/src/compiler/clc/mesa_clc'
vtn_bindgen2 = '$PWD/tools/src/compiler/spirv/vtn_bindgen2'
asahi_clc = '$PWD/tools/src/asahi/clc/asahi_clc'
X
PKG_CONFIG_LIBDIR=/usr/lib64/pkgconfig:/usr/share/pkgconfig meson setup b64 "${common[@]}" "${drivers[@]}" --libdir=lib64
ninja -C b64 %{?_smp_mflags}
cat > i686.cross <<X
[binaries]
c = ['gcc', '-m32']
cpp = ['g++', '-m32']
ar = 'ar'
strip = 'strip'
pkg-config = 'pkg-config'
[properties]
pkg_config_libdir = '/usr/lib/pkgconfig:/usr/share/pkgconfig'
[host_machine]
system = 'linux'
cpu_family = 'x86'
cpu = 'i686'
endian = 'little'
X
meson setup b32 "${common[@]}" "${drivers[@]}" --libdir=lib --cross-file i686.cross
ninja -C b32 %{?_smp_mflags}

%install
L=%{buildroot}%{layer}
DESTDIR=$L meson install -C b64 --no-rebuild
DESTDIR=$L meson install -C b32 --no-rebuild
rm -rf $L/usr/include $L/usr/lib64/pkgconfig $L/usr/lib/pkgconfig
echo %{commit} > $L/.aurora-mesa-commit
mkdir -p %{buildroot}/usr/share/guestos/aurora-fex-mesa
install -Dm644 %{SOURCE1} %{buildroot}%{_unitdir}/aurora-fex-mesa.service
install -Dm644 %{SOURCE2} %{buildroot}%{_presetdir}/80-aurora-fex-mesa.preset

%check
for f in %{buildroot}%{layer}/usr/lib64/libgallium-*.so %{buildroot}%{layer}/usr/lib64/libvulkan_asahi.so; do
  file -L "$f" | grep -q 'ELF 64-bit LSB shared object, x86-64'
done
for f in %{buildroot}%{layer}/usr/lib/libgallium-*.so %{buildroot}%{layer}/usr/lib/libvulkan_asahi.so; do
  file -L "$f" | grep -q 'ELF 32-bit LSB shared object, Intel'
done
# Nothing in the layer may need a runtime whose soname follows the guest's release.
if find %{buildroot}%{layer} -name '*.so*' -type f -exec readelf -d {} + |
    grep -E 'NEEDED.*(libLLVM|libSPIRV-Tools|libsensors|libunwind)'; then
  echo 'guest driver needs a release-specific runtime' >&2
  exit 1
fi

%post
%systemd_post aurora-fex-mesa.service
if [ $1 -eq 1 ] && [ -d /run/systemd/system ]; then
  systemctl start aurora-fex-mesa.service >/dev/null 2>&1 || :
fi
%preun
%systemd_preun aurora-fex-mesa.service
%postun
%systemd_postun_with_restart aurora-fex-mesa.service

%files
%{layer}
%dir /usr/share/guestos/aurora-fex-mesa
%{_unitdir}/aurora-fex-mesa.service
%{_presetdir}/80-aurora-fex-mesa.preset

%changelog
* Tue Oct 20 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.3.0-2.aurora
- x86_64/i686 guest graphics provider for FEX, in lockstep with mesa-aurora.
