%global commit 14b6b0c453146a09d08f377e9a6c9905d64e442a
%global debug_package %{nil}
Name: mesa-aurora
Version: 26.3.0
Release: 9%{?dist}.aurora
Summary: Aurora Asahi OpenGL and Vulkan drivers
License: MIT
URL: https://github.com/aurora-silicon/mesa
Source0: mesa-aurora-%{commit}.tar.gz
ExclusiveArch: aarch64
BuildRequires: gcc gcc-c++ clang clang-devel systemd-devel llvm-devel lld rust cargo bindgen-cli cbindgen
BuildRequires: meson ninja-build python3-mako python3-pyyaml python3-packaging
BuildRequires: bison flex elfutils-libelf-devel
BuildRequires: libclc-devel spirv-llvm-translator-devel spirv-tools-devel glslang-devel
BuildRequires: libdrm-devel expat-devel libglvnd-devel libX11-devel libxcb-devel
BuildRequires: libXext-devel libXfixes-devel libXrandr-devel libxshmfence-devel libXxf86vm-devel
BuildRequires: wayland-devel wayland-protocols-devel vulkan-headers vulkan-loader-devel
BuildRequires: libdisplay-info-devel lm_sensors-devel zlib-ng-compat-devel libzstd-devel xcb-util-keysyms-devel

%description
Aurora's native Asahi Gallium and Honeykrisp drivers. Compiler tools are built
first; installed drivers do not link to LLVM or SPIRV-Tools.

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

%prep
%autosetup -n mesa-%{commit} -p1

%build
options=(--prefix=/usr --libdir=lib64 --libexecdir=libexec --buildtype=release --wrap-mode=nodownload
  -Dplatforms=x11,wayland -Dgallium-drivers=asahi,zink,softpipe -Dvulkan-drivers=asahi
  -Degl=enabled -Dgbm=enabled -Dglx=dri -Dgles1=enabled -Dgles2=enabled
  -Dglvnd=enabled -Dvideo-codecs=all -Dvulkan-layers=
  -Dexpat=enabled -Dzstd=enabled -Dlmsensors=enabled -Dlibunwind=disabled -Dvalgrind=disabled)
meson setup tools "${options[@]}" -Dllvm=enabled -Dbuild-tests=false
ninja -C tools %{?_smp_mflags} src/compiler/clc/mesa_clc src/compiler/spirv/vtn_bindgen2 src/asahi/clc/asahi_clc
printf "[binaries]\nmesa_clc = '%s'\nvtn_bindgen2 = '%s'\nasahi_clc = '%s'\n" \
  "$PWD/tools/src/compiler/clc/mesa_clc" "$PWD/tools/src/compiler/spirv/vtn_bindgen2" "$PWD/tools/src/asahi/clc/asahi_clc" > tools.ini
meson setup build "${options[@]}" --native-file tools.ini -Dllvm=disabled -Dspirv-tools=disabled -Dmesa-clc=system -Dprecomp-compiler=system -Dbuild-tests=true
ninja -C build %{?_smp_mflags}

%check
meson test -C build --print-errorlogs --num-processes 4

%install
DESTDIR=%{buildroot} meson install -C build --no-rebuild
while IFS= read -r binary; do
  readelf -d "$binary" > dependencies.txt
  if grep -Eq 'NEEDED.*(libLLVM|libSPIRV-Tools)' dependencies.txt; then
    echo "Compiler runtime dependency in $binary" >&2; exit 1
  fi
done < <(find %{buildroot} -type f -name '*.so*')
find %{buildroot} -type f -o -type l | sed 's@%{buildroot}@@' > all.files
grep -E 'libvulkan_asahi\.so|vulkan/icd.d/.*asahi.*json' all.files > vulkan.files
grep -vE 'libvulkan_asahi\.so|vulkan/icd.d/.*asahi.*json' all.files > dri.files

%files -n mesa-aurora-dri-drivers -f dri.files
%files -n mesa-aurora-vulkan-drivers -f vulkan.files

%changelog
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
