%global commit cf4e08105dfa526b8874318b6a52b3ce948f6297
%global debug_package %{nil}
Name: mesa-aurora
Version: 26.3.0
Release: 13%{?dist}.aurora
Summary: Aurora Asahi OpenGL and Vulkan drivers
License: MIT
URL: https://github.com/aurora-silicon/mesa
Source0: mesa-aurora-%{commit}.tar.gz
ExclusiveArch: aarch64
BuildRequires: gcc gcc-c++ clang clang-devel systemd-devel llvm-devel lld rust cargo bindgen-cli cbindgen
BuildRequires: meson ninja-build python3-mako python3-pyyaml python3-packaging
BuildRequires: bison flex binutils elfutils-libelf-devel opencl-headers
# Fedora 45 ships the LLVM 23 libclc without pkg-config data; the LLVM 22
# libclc22-devel still provides it there, and Rusticl needs the same libclc.
BuildRequires: pkgconfig(libclc)
BuildRequires: spirv-llvm-translator-devel spirv-tools-devel glslang-devel
BuildRequires: libdrm-devel expat-devel libglvnd-devel libX11-devel libxcb-devel
BuildRequires: libXext-devel libXfixes-devel libXrandr-devel libxshmfence-devel libXxf86vm-devel
BuildRequires: wayland-devel wayland-protocols-devel vulkan-headers vulkan-loader-devel
BuildRequires: libdisplay-info-devel lm_sensors-devel zlib-ng-compat-devel libzstd-devel xcb-util-keysyms-devel

%description
Aurora's native Asahi Gallium and Honeykrisp drivers. Compiler tools are built
first; GL/Vulkan drivers do not link to LLVM or SPIRV-Tools. Rusticl OpenCL
is packaged separately with its compiler runtime dependencies.

%package -n mesa-aurora-dri-drivers
Summary: Aurora Mesa OpenGL, EGL and GBM
Provides: mesa-dri-drivers = %{version}-%{release}
Provides: mesa-dri-drivers%{?_isa} = %{version}-%{release}
Provides: mesa-libEGL = %{version}-%{release}
Provides: mesa-libEGL%{?_isa} = %{version}-%{release}
Provides: mesa-libGL = %{version}-%{release}
Provides: mesa-libGL%{?_isa} = %{version}-%{release}
Provides: mesa-libgbm = %{version}-%{release}
Provides: mesa-libgbm%{?_isa} = %{version}-%{release}
Provides: mesa-libglapi = %{version}-%{release}
Provides: mesa-libglapi%{?_isa} = %{version}-%{release}
Provides: mesa-libgallium = %{version}-%{release}
Provides: mesa-libgallium%{?_isa} = %{version}-%{release}
Obsoletes: mesa-dri-drivers < %{version}-%{release}
Obsoletes: mesa-libEGL < %{version}-%{release}
Obsoletes: mesa-libGL < %{version}-%{release}
Obsoletes: mesa-libgbm < %{version}-%{release}
Obsoletes: mesa-libglapi < %{version}-%{release}
Obsoletes: mesa-libgallium < %{version}-%{release}
Requires: libglvnd-egl libglvnd-glx

%description -n mesa-aurora-dri-drivers
Aurora Asahi, Zink and software OpenGL drivers, plus EGL and GBM integration.

%package -n mesa-aurora-vulkan-drivers
Summary: Aurora Honeykrisp Vulkan driver
Provides: mesa-vulkan-drivers = %{version}-%{release}
Provides: mesa-vulkan-drivers%{?_isa} = %{version}-%{release}
Obsoletes: mesa-vulkan-drivers < %{version}-%{release}
Requires: vulkan-loader

%description -n mesa-aurora-vulkan-drivers
Native Honeykrisp Vulkan driver for Aurora Apple Silicon kernels.

# The replaced mesa-vulkan-drivers also shipped lavapipe, and applications
# link it directly (libvulkan_lvp.so). It needs LLVM, so it is split out to
# keep the native Vulkan driver free of the compiler runtime.
%package -n mesa-aurora-vulkan-lavapipe
Summary: Aurora Mesa lavapipe software Vulkan driver
Requires: vulkan-loader
Obsoletes: mesa-vulkan-drivers < %{version}-%{release}

%description -n mesa-aurora-vulkan-lavapipe
CPU-based Vulkan driver built from the same source as the native drivers.

# Development files used to be swept into dri-drivers, leaving Fedora's
# devel packages installed with exact Requires on the replaced runtime EVR.
%package -n mesa-aurora-devel
Summary: Aurora Mesa EGL, GL and GBM development files
Requires: mesa-aurora-dri-drivers%{?_isa} = %{version}-%{release}
Requires: libglvnd-devel%{?_isa} >= 1:1.3.2
Requires: mesa-khr-devel%{?_isa}
Provides: mesa-libEGL-devel = %{version}-%{release}
Provides: mesa-libEGL-devel%{?_isa} = %{version}-%{release}
Provides: mesa-libGL-devel = %{version}-%{release}
Provides: mesa-libGL-devel%{?_isa} = %{version}-%{release}
Provides: mesa-libgbm-devel = %{version}-%{release}
Provides: mesa-libgbm-devel%{?_isa} = %{version}-%{release}
Obsoletes: mesa-libEGL-devel < %{version}-%{release}
Obsoletes: mesa-libGL-devel < %{version}-%{release}
Obsoletes: mesa-libgbm-devel < %{version}-%{release}

%description -n mesa-aurora-devel
Headers, pkg-config files and GBM linker interface for the matching Aurora Mesa.

%package -n mesa-aurora-libOpenCL
Summary: Aurora Mesa Rusticl OpenCL driver
Requires: mesa-aurora-dri-drivers%{?_isa} = %{version}-%{release}
Requires: (ocl-icd%{?_isa} or OpenCL-ICD-Loader%{?_isa})
Requires: opencl-filesystem
%if 0%{?fedora} >= 45
Requires: libclc22%{?_isa}
%else
Requires: libclc%{?_isa}
%endif
Provides: mesa-libOpenCL = %{version}-%{release}
Provides: mesa-libOpenCL%{?_isa} = %{version}-%{release}
Obsoletes: mesa-libOpenCL < %{version}-%{release}

%description -n mesa-aurora-libOpenCL
Rusticl built from the same source as the native drivers. Replaces the older
OpenCL package, including its exact dependency on the old GBM version.

%package -n mesa-aurora-libOpenCL-devel
Summary: Linker interface for Aurora Mesa Rusticl
Requires: mesa-aurora-libOpenCL%{?_isa} = %{version}-%{release}
Provides: mesa-libOpenCL-devel = %{version}-%{release}
Provides: mesa-libOpenCL-devel%{?_isa} = %{version}-%{release}
Obsoletes: mesa-libOpenCL-devel < %{version}-%{release}

%description -n mesa-aurora-libOpenCL-devel
Linker interface for the matching Aurora Rusticl OpenCL library.

%prep
%autosetup -n mesa-%{commit} -p1

%build
# Release archives have no .git directory; stamp both Meson builds explicitly.
export MESA_GIT_SHA1_OVERRIDE=%{commit}
options=(--prefix=/usr --libdir=lib64 --libexecdir=libexec --buildtype=release --wrap-mode=nodownload
  -Dplatforms=x11,wayland -Dgallium-drivers=asahi,zink,softpipe -Dvulkan-drivers=asahi
  -Degl=enabled -Dgbm=enabled -Dglx=dri -Dgles1=enabled -Dgles2=enabled
  -Dglvnd=enabled -Dvideo-codecs=all -Dvulkan-layers=
  -Dexpat=enabled -Dzstd=enabled -Dlmsensors=enabled -Dlibunwind=disabled -Dvalgrind=disabled)
meson setup tools "${options[@]/#-Dvulkan-drivers=asahi/-Dvulkan-drivers=asahi,swrast}" -Dllvm=enabled -Dgallium-rusticl=true -Dbuild-tests=false
ninja -C tools %{?_smp_mflags} src/compiler/clc/mesa_clc src/compiler/spirv/vtn_bindgen2 src/asahi/clc/asahi_clc src/gallium/targets/rusticl/libRusticlOpenCL.so.1.0.0 \
  src/gallium/targets/lavapipe/libvulkan_lvp.so src/gallium/targets/lavapipe/lvp_icd.aarch64.json
printf "[binaries]\nmesa_clc = '%s'\nvtn_bindgen2 = '%s'\nasahi_clc = '%s'\n" \
  "$PWD/tools/src/compiler/clc/mesa_clc" "$PWD/tools/src/compiler/spirv/vtn_bindgen2" "$PWD/tools/src/asahi/clc/asahi_clc" > tools.ini
meson setup build "${options[@]}" --native-file tools.ini -Dgallium-rusticl=false -Dllvm=disabled -Dspirv-tools=disabled -Dmesa-clc=system -Dprecomp-compiler=system -Dbuild-tests=true
ninja -C build %{?_smp_mflags}

%check
# RPM phases use separate shells. meson test rebuilds the always-stale Git
# header, so retain the archive identity here as well as in the build phase.
export MESA_GIT_SHA1_OVERRIDE=%{commit}
meson test -C build --print-errorlogs --num-processes 4

%install
DESTDIR=%{buildroot} meson install -C build --no-rebuild
# Install only Rusticl from the LLVM-enabled tree; GL/Vulkan use build/.
install -Dm755 tools/src/gallium/targets/rusticl/libRusticlOpenCL.so.1.0.0 %{buildroot}%{_libdir}/libRusticlOpenCL.so.1.0.0
ln -s libRusticlOpenCL.so.1.0.0 %{buildroot}%{_libdir}/libRusticlOpenCL.so.1
ln -s libRusticlOpenCL.so.1 %{buildroot}%{_libdir}/libRusticlOpenCL.so
install -Dm755 tools/src/gallium/targets/lavapipe/libvulkan_lvp.so %{buildroot}%{_libdir}/libvulkan_lvp.so
install -Dm644 tools/src/gallium/targets/lavapipe/lvp_icd.aarch64.json %{buildroot}%{_datadir}/vulkan/icd.d/lvp_icd.aarch64.json
grep -F '"library_path": "%{_libdir}/libvulkan_lvp.so"' %{buildroot}%{_datadir}/vulkan/icd.d/lvp_icd.aarch64.json
install -Dm644 tools/src/gallium/targets/rusticl/rusticl.icd %{buildroot}%{_sysconfdir}/OpenCL/vendors/rusticl.icd
while IFS= read -r binary; do
  # Rusticl compiles OpenCL programs and lavapipe JIT-compiles shaders at
  # runtime; both legitimately need LLVM.
  case "$binary" in */libRusticlOpenCL.so*|*/libvulkan_lvp.so) continue ;; esac
  readelf -d "$binary" > dependencies.txt
  if grep -Eq 'NEEDED.*(libLLVM|libSPIRV-Tools)' dependencies.txt; then
    echo "Compiler runtime dependency in $binary" >&2; exit 1
  fi
done < <(find %{buildroot} -type f -name '*.so*')
find %{buildroot} -type f -o -type l | sed 's@%{buildroot}@@' > all.files
grep -E 'libvulkan_asahi\.so|vulkan/icd.d/.*asahi.*json' all.files > vulkan.files
grep -E '^/usr/include/|/pkgconfig/|^/usr/lib64/libgbm\.so$' all.files > devel.files
grep -vE 'libvulkan_asahi\.so|vulkan/icd.d/.*asahi.*json|libvulkan_lvp\.so|vulkan/icd.d/lvp_icd|libRusticlOpenCL|/OpenCL/vendors/' all.files | grep -vxF -f devel.files > dri.files
# Check the installed driverInfo, not just the build environment variable.
strings %{buildroot}%{_libdir}/libvulkan_asahi.so | grep -F "Mesa " | grep -F "(git-$(echo %{commit} | cut -c1-10)), Borealis"

%files -n mesa-aurora-dri-drivers -f dri.files
%files -n mesa-aurora-vulkan-drivers -f vulkan.files
%files -n mesa-aurora-vulkan-lavapipe
%{_libdir}/libvulkan_lvp.so
%{_datadir}/vulkan/icd.d/lvp_icd.aarch64.json
%files -n mesa-aurora-devel -f devel.files
%files -n mesa-aurora-libOpenCL
%{_libdir}/libRusticlOpenCL.so.1*
%{_sysconfdir}/OpenCL/vendors/rusticl.icd
%files -n mesa-aurora-libOpenCL-devel
%{_libdir}/libRusticlOpenCL.so

%changelog
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.3.0-13
- Rebuild in lockstep with the mesa-aurora-fex-guest upgrade fix.

* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.3.0-12
- Ship lavapipe as mesa-aurora-vulkan-lavapipe. The replaced
  mesa-vulkan-drivers carried libvulkan_lvp.so and installed applications
  require it, so the migration otherwise removes them.
- Build on Fedora 45, where libclc pkg-config data comes from libclc22-devel.

* Sat Oct 31 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-11
- Embed the pinned Mesa commit in native driverInfo.
- Replace legacy OpenCL/devel packages with matching functional subpackages.

* Fri Oct 30 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.3.0-10
- Track aurora-silicon/mesa aurora-wip at cf4e081.
- Upstream head: Merge pull request #102 from aurora-silicon/feat/borealis-driver-id
- Borealis reports VK_DRIVER_ID_AURORA_BOREALIS and conformanceVersion 0.0.0.0.

* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-9
- Track aurora-silicon/mesa aurora-wip at 14b6b0c.
- Upstream head: Merge pull request #110 from aurora-silicon/fix/agx3-cube-scratch-validate

* Wed Oct 28 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-8
- Track aurora-silicon/mesa aurora-wip at 108c721.
- Upstream head: Merge pull request #93 from aurora-silicon/fix/hk-sparse-scratch-reservation-release

* Mon Oct 26 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-7
- Track aurora-silicon/mesa aurora-wip at f2c9dc3.
- Upstream head: Merge pull request #62 from aurora-silicon/perf/g17-finalized-submit-20261024

* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-6
- Track aurora-silicon/mesa aurora-wip at 2e0bdb2.
- Upstream head: Merge pull request #54 from aurora-silicon/perf/agx2-refmac-parity-20261023

* Thu Oct 22 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-4
- Track aurora-silicon/mesa aurora-wip at c4e3095, matched to the Linux 7.3 kernel.
- Link the driver tests that replace functions with --wrap without LTO.

* Tue Oct 20 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-3
- Pair the current Aurora userspace with the integration kernel.
- Use the merged sampler-bias test fix.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-1.aurora
- Initial native Fedora Aurora graphics stack.
