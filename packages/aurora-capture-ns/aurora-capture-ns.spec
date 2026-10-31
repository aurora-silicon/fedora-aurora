%global commit f843fd3d053f716222caa7286a2095a9ffb8e762
%global libane_commit 1adf2ee392ef7d3d64a24743d293dbc1670f0e8b
%global rnnoise_commit 6cbfd53eb348a8d394e0757b4025c6ded34eb2b6
%global libdf_commit d375b2d8309e0935d165700c91da9de862a99c31
Name: aurora-capture-ns
Version: 0.1.0
Release: 1%{?dist}
Summary: Opt-in capture-only RNNoise and DeepFilterNet filter
License: MIT
URL: https://github.com/aurora-silicon/capture-ns
Source0: aurora-capture-ns-%{commit}.tar.gz
Source1: libane-%{libane_commit}.tar.gz
Source2: rnnoise-%{rnnoise_commit}.tar.gz
Source3: libdf-%{libdf_commit}.tar.gz
Source4: df-Cargo.lock
Source5: aurora-capture-ns
Patch0: libdf-external-model.patch
ExclusiveArch: aarch64
BuildRequires: libdrm-devel
BuildRequires: gcc make autoconf automake libtool pkgconf-pkg-config
BuildRequires: openssl-devel ladspa-devel python3 rust cargo
Requires: pipewire python3 aurora-models
Requires: aurora-rnnoise = %{version}-%{release}
Requires: aurora-libdf = %{version}-%{release}

%description
An explicitly started PipeWire capture filter. Choose its virtual microphone
in the recording application. Installation never starts it or changes a
default device. Uses libane's CPU fallback API; native ANE models are not
available in this revision. No playback or recording occurs at install.

%package -n aurora-rnnoise
Summary: Pinned RNNoise library for Aurora capture demos
License: BSD-3-Clause
%description -n aurora-rnnoise
RNNoise v0.1.1 (6cbfd53eb348a8d394e0757b4025c6ded34eb2b6) in a private library path.
The BSD-3-Clause built-in weight arrays are included under COPYING.

%package -n aurora-libdf
Summary: Pinned libDF C API for Aurora capture demos
License: MIT OR Apache-2.0
%description -n aurora-libdf
DeepFilterNet libDF (d375b2d8309e0935d165700c91da9de862a99c31) in a private library path.
The embedded default model is disabled. Weights are fetched explicitly by
aurora-model-fetch and are not included in this library.

%prep
%setup -q -n capture-ns-%{commit} -a 1 -a 2 -a 3
cp %{SOURCE4} DeepFilterNet-%{libdf_commit}/Cargo.lock
pushd DeepFilterNet-%{libdf_commit}
%patch -P 0 -p1
popd

%build
make -C omarchy-ane-%{libane_commit}/libane %{?_smp_mflags} CFLAGS="%{optflags} -fPIC"
pushd rnnoise-%{rnnoise_commit}
./autogen.sh
%configure --disable-examples
%make_build
popd
pushd DeepFilterNet-%{libdf_commit}
CARGO_PROFILE_RELEASE_OPT_LEVEL=2 CARGO_PROFILE_RELEASE_LTO=false CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-%{_smp_build_ncpus}}" cargo build --release --locked -p deep_filter --no-default-features --features capi
popd
%make_build LIBANE_DIR=$PWD/omarchy-ane-%{libane_commit}/libane LIBANE_LIB=$PWD/omarchy-ane-%{libane_commit}/libane/libane.a CFLAGS="%{optflags}" LDFLAGS="%{build_ldflags}"

%check
export AURORA_RNNOISE_LIBRARY=$PWD/rnnoise-%{rnnoise_commit}/.libs/librnnoise.so
export AURORA_DF_LIBRARY=$PWD/DeepFilterNet-%{libdf_commit}/target/release/libdf.so
export AURORA_DF_MODEL=$PWD/DeepFilterNet-%{libdf_commit}/models/DeepFilterNet3_onnx.tar.gz
export AURORA_RNNOISE_MODEL=$PWD/build/rnnoise-v011.txt
python3 tools/export_rnnoise.py rnnoise-%{rnnoise_commit}/src/rnn_data.c "$AURORA_RNNOISE_MODEL"
make %{?_smp_mflags} LIBANE_DIR=$PWD/omarchy-ane-%{libane_commit}/libane LIBANE_LIB=$PWD/omarchy-ane-%{libane_commit}/libane/libane.a build/test-stream build/test-engine build/test-ladspa
build/test-stream
build/test-engine
build/test-ladspa build/libaurora_capture_ns.so
python3 -m unittest discover -s tests -p test_config.py -v

%install
install -Dm755 build/libaurora_capture_ns.so %{buildroot}%{_libdir}/ladspa/libaurora_capture_ns.so
install -Dm755 tools/aurora-capture-ns %{buildroot}%{_libexecdir}/aurora-capture-ns/launcher.py
install -Dm755 %{SOURCE5} %{buildroot}%{_bindir}/aurora-capture-ns
sed -i -e 's|@FETCH@|%{_bindir}/aurora-model-fetch|g' -e 's|@RNNOISE@|%{_libdir}/aurora-capture-ns/librnnoise.so.0|g' -e 's|@LIBDF@|%{_libdir}/aurora-capture-ns/libdf.so|g' -e 's|@LAUNCHER@|%{_libexecdir}/aurora-capture-ns/launcher.py|g' -e 's|@PLUGIN@|%{_libdir}/ladspa/libaurora_capture_ns.so|g' %{buildroot}%{_bindir}/aurora-capture-ns
install -d %{buildroot}%{_libdir}/aurora-capture-ns
cp -a rnnoise-%{rnnoise_commit}/.libs/librnnoise.so* %{buildroot}%{_libdir}/aurora-capture-ns/
install -m755 DeepFilterNet-%{libdf_commit}/target/release/libdf.so %{buildroot}%{_libdir}/aurora-capture-ns/
install -Dm644 omarchy-ane-%{libane_commit}/LICENSE %{buildroot}%{_licensedir}/%{name}/libane-LICENSE
install -Dm644 rnnoise-%{rnnoise_commit}/COPYING %{buildroot}%{_licensedir}/aurora-rnnoise/COPYING
install -Dm644 DeepFilterNet-%{libdf_commit}/LICENSE-MIT %{buildroot}%{_licensedir}/aurora-libdf/LICENSE-MIT
install -Dm644 DeepFilterNet-%{libdf_commit}/LICENSE-APACHE %{buildroot}%{_licensedir}/aurora-libdf/LICENSE-APACHE
# The launcher defaults to /usr/local, so pass the packaged plugin explicitly.
%files
%license LICENSE %{_licensedir}/%{name}/libane-LICENSE
%doc README.md NOTICES.md docs/
%{_bindir}/aurora-capture-ns
%{_libexecdir}/aurora-capture-ns/
%{_libdir}/ladspa/libaurora_capture_ns.so
%files -n aurora-rnnoise
%license %{_licensedir}/aurora-rnnoise/COPYING
%dir %{_libdir}/aurora-capture-ns
%{_libdir}/aurora-capture-ns/librnnoise.so*
%files -n aurora-libdf
%license %{_licensedir}/aurora-libdf/
%dir %{_libdir}/aurora-capture-ns
%{_libdir}/aurora-capture-ns/libdf.so
%changelog
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-1
- Package the pinned capture stack, with external SHA-256 checked models.
