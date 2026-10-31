%global commit e65f3c4423baae5898e40458d8cb1d192897172e
%global libane_commit 1adf2ee392ef7d3d64a24743d293dbc1670f0e8b
Name: whisper-cpp-aurora
Version: 1.9.5
Release: 1%{?dist}
Summary: Aurora Whisper file transcription with Vulkan and the Linux ANE adapter
License: MIT
URL: https://github.com/aurora-silicon/whisper.cpp
Source0: whisper.cpp-aurora-%{commit}.tar.gz
Source1: libane-%{libane_commit}.tar.gz
Source2: whisper.cpp-aurora
ExclusiveArch: aarch64
BuildRequires: libdrm-devel
BuildRequires: gcc gcc-c++ make cmake ninja-build glslc vulkan-headers vulkan-loader-devel spirv-headers-devel python3
Requires: python3 python3-numpy vulkan-tools aurora-models
Recommends: mil-hwx-compiler
Provides: whisper.cpp-aurora = %{version}-%{release}

%description
File transcription using the Aurora Whisper fork. Vulkan and CPU backends
are built together; the Linux libane adapter accepts explicitly supplied,
locally compiled open encoder bundles. No weights, service, microphone or
playback integration are installed. Use whisper.cpp-aurora --engine auto
-f FILE.wav to fetch the checked MIT tiny.en model and transcribe a file.

%prep
%setup -q -n whisper.cpp-%{commit} -a 1

%build
make -C omarchy-ane-%{libane_commit}/libane %{?_smp_mflags} CFLAGS="%{optflags} -fPIC"
%cmake -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_VULKAN=ON -DWHISPER_ANE=ON -DWHISPER_SDL2=OFF -DWHISPER_COREML=OFF -DWHISPER_BUILD_SERVER=OFF -DWHISPER_BUILD_TESTS=ON -DLIBANE_INCLUDE_DIR=$PWD/omarchy-ane-%{libane_commit}/libane -DLIBANE_LIBRARY=$PWD/omarchy-ane-%{libane_commit}/libane/libane.a -DWHISPER_ANE_WORKER_PATH=%{_datadir}/whisper-aurora/ane/worker.py
%cmake_build

%check
%ctest -L unit
python3 tests/ane/test_worker.py

%install
install -Dm755 %{_vpath_builddir}/bin/whisper-cli %{buildroot}%{_bindir}/whisper-cli-aurora
install -Dm755 %{_vpath_builddir}/bin/whisper-bench %{buildroot}%{_bindir}/whisper-bench-aurora
install -Dm644 models/ane/worker.py %{buildroot}%{_datadir}/whisper-aurora/ane/worker.py
install -Dm755 %{SOURCE2} %{buildroot}%{_bindir}/whisper.cpp-aurora
sed -i -e 's|@CLI@|%{_bindir}/whisper-cli-aurora|g' -e 's|@FETCH@|%{_bindir}/aurora-model-fetch|g' -e 's|@VULKANINFO@|%{_bindir}/vulkaninfo|g' %{buildroot}%{_bindir}/whisper.cpp-aurora
install -Dm644 omarchy-ane-%{libane_commit}/LICENSE %{buildroot}%{_licensedir}/%{name}/libane-LICENSE
%files
%license LICENSE
%license %{_licensedir}/%{name}/libane-LICENSE
%doc docs/ane/
%{_bindir}/whisper-cli-aurora
%{_bindir}/whisper-bench-aurora
%{_bindir}/whisper.cpp-aurora
%{_datadir}/whisper-aurora/
%changelog
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.9.5-1
- Build Vulkan and the Linux ANE adapter, keeping every demo explicit.
