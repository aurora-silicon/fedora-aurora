%global commit b318fcf4bd5e563e6ebc53953567a12ab39dcb24

Name: libva-v4l2-request
Version: 1.3.r11
Release: 1%{?dist}.aurora
Summary: VA-API driver for V4L2 stateless request decoders
License: GPL-3.0-or-later
URL: https://github.com/aurora-silicon/libva-v4l2_request
Source0: %{name}-%{commit}.tar.gz
ExclusiveArch: aarch64

BuildRequires: gcc
BuildRequires: kernel-headers
BuildRequires: libdrm-devel
BuildRequires: libva-devel
BuildRequires: meson
BuildRequires: ninja-build
BuildRequires: pkgconf-pkg-config
Requires: libva%{?_isa}
Provides: libva-v4l2_request = %{version}-%{release}

%description
A VA-API decode driver that translates VA picture parameters into Linux V4L2
stateless Request API controls. Aurora uses it with the Apple Video Decoder for
H.264, HEVC, VP9 and AV1 according to the capabilities reported by the kernel.

%prep
%autosetup -n libva-v4l2_request-%{commit}

%build
%meson -Dvendor-string=Aurora -Dstrip=false
%meson_build

%check
%meson_test --print-errorlogs --num-processes 4
strings %{_vpath_builddir}/src/v4l2_request_drv_video.so | grep -Fq 'v4l2-request (Aurora %{version})'

%install
%meson_install
ln -s v4l2_request_drv_video.so %{buildroot}%{_libdir}/dri/asahi_drv_video.so

%files
%license COPYING
%doc README README.md
%{_libdir}/dri/v4l2_request_drv_video.so
%{_libdir}/dri/asahi_drv_video.so

%changelog
* Sat Nov 07 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 1.3.r11-1
- Add the V4L2 Request API VA-API backend for Aurora AVD decode
