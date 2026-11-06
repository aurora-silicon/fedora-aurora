%global commit 4f60c51f7841dd74bb61c94a4ad31e630bbdab01
Name: libva-v4l2-request-avd
Version: 1.3.r11
Release: 1%{?dist}.aurora
Summary: VA-API driver for the AVD V4L2 Request decoder
License: GPL-3.0-or-later
URL: https://github.com/omacom/libva-v4l2_request
Source0: https://codeload.github.com/omacom/libva-v4l2_request/tar.gz/%{commit}#/%{name}-%{commit}.tar.gz
Patch0: 0001-offline-test-portability.patch
ExclusiveArch: aarch64
BuildRequires: gcc meson ninja-build pkgconf-pkg-config python3 libtsan
BuildRequires: kernel-headers >= 6.5
BuildRequires: pkgconfig(libva) pkgconfig(libdrm)
Requires: libva%{?_isa}

%description
VA-API decode driver for stateless V4L2 Request API devices, pinned to the
public AVD fixes branch. The package installs the explicit v4l2_request driver
and an asahi loader alias; it does not install firmware, browser preferences,
environment overrides, or sandbox exceptions.

%prep
%autosetup -n libva-v4l2_request-%{commit} -p1

%build
%meson -Ddriverdir=%{_libdir}/dri -Dstrip=false \
  -Dcodec_h264=enabled -Dcodec_hevc=enabled \
  -Dcodec_vp9=enabled -Dcodec_av1=enabled
%meson_build

%check
%meson_test --print-errorlogs --num-processes 4

%install
%meson_install
ln -s v4l2_request_drv_video.so \
  %{buildroot}%{_libdir}/dri/asahi_drv_video.so

%files
%license COPYING
%doc README.md docs/SUPPORT.md
%{_libdir}/dri/v4l2_request_drv_video.so
%{_libdir}/dri/asahi_drv_video.so

%changelog
* Sat Nov 07 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 1.3.r11-1
- Package the hardware-qualified AVD VA-API driver system-wide.
- Select it automatically for the AGX render node through a relative alias.
