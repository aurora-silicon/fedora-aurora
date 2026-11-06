%global commit 7e3cb89d69e83d0d0ed589b27edb7d2ed8ea1ce7
Name: libva-v4l2-request-avd
Version: 1.3.r11
Release: 1%{?dist}.aurora
Summary: VA-API driver for V4L2 stateless decoders including Apple AVD
License: GPL-3.0-or-later
URL: https://github.com/omacom/libva-v4l2_request
Source0: %{name}-%{commit}.tar.gz
ExclusiveArch: aarch64

BuildRequires: gcc
BuildRequires: meson
BuildRequires: ninja-build
BuildRequires: pkgconfig(libva) >= 1.7.0
BuildRequires: pkgconfig(libdrm)
Requires: libva%{?_isa}
Recommends: avd-fw
Provides: libva-v4l2-request = %{version}-%{release}

%description
VA-API decode driver translating VLD calls into the Linux V4L2 stateless
request API. This build carries the maintained Apple Video Decoder fixes,
truthful per-codec 10-bit profile probing, stable early-export DMA-BUF
surfaces for browsers and linear NV12/P010 DRM PRIME export.

The package installs the explicit v4l2_request driver and the automatic
asahi driver-name alias used by native desktop applications. It does not
change browser sandbox settings or install a kernel driver or firmware.

%prep
%autosetup -n libva-v4l2_request-%{commit}

%build
%meson -Ddriverdir=%{_libdir}/dri -Dvendor-string='Fedora Aurora' -Dstrip=false
%meson_build

%check
%meson_test

%install
%meson_install
ln -s v4l2_request_drv_video.so \
  %{buildroot}%{_libdir}/dri/asahi_drv_video.so

%files
%license COPYING
%doc README README.md NEWS docs/SUPPORT.md docs/DIAGNOSTICS.md
%{_libdir}/dri/v4l2_request_drv_video.so
%{_libdir}/dri/asahi_drv_video.so

%changelog
* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 1.3.r11-1
- Add the maintained V4L2-request VA-API bridge for native desktop clients.
- Discover it automatically on AGX and brand diagnostics as Fedora Aurora.
- Gate HEVC Main10, VP9 Profile 2 and AV1 10-bit output on codec/P010 probes.
