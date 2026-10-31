%global commit 4f60c51f7841dd74bb61c94a4ad31e630bbdab01
Name: libva-v4l2-request
Version: 1.3.r11
Release: 3%{?dist}
Summary: Application-selected VA-API driver for stateless V4L2 decoders
License: GPL-3.0-or-later
URL: https://github.com/omacom/libva-v4l2_request
Source0: https://github.com/omacom/libva-v4l2_request/archive/%{commit}.tar.gz#/%{name}-%{commit}.tar.gz
Source1: avd-vaapi.in
Patch0: 0001-offline-test-portability.patch
ExclusiveArch: aarch64
BuildRequires: libtsan
BuildRequires: gcc meson ninja-build pkgconf-pkg-config python3
BuildRequires: kernel-headers >= 6.5
BuildRequires: pkgconfig(libva) pkgconfig(libdrm)
Requires: libva%{?_isa}
# This module must not satisfy a system driver dependency.
%global __provides_exclude_from ^%{_libdir}/aurora-avd/va/.*$

%description
Pinned VA-API bridge for stateless V4L2 Request API decoders, including
AVD fixes. avd-vaapi selects the private driver for one application.
No environment.d, profile.d, browser preference or sandbox override is
installed. This upstream pin is GPL-3.0-or-later, not MIT or LGPL.

%prep
%autosetup -n libva-v4l2_request-%{commit} -p1

%build
%meson -Ddriverdir=%{_libdir}/aurora-avd/va -Dstrip=false \
  -Dcodec_h264=enabled -Dcodec_hevc=enabled -Dcodec_vp9=enabled -Dcodec_av1=enabled
%meson_build

%install
%meson_install
mkdir -p %{buildroot}%{_bindir}
sed 's|@DRIVERDIR@|%{_libdir}/aurora-avd/va|g' %{SOURCE1} > %{buildroot}%{_bindir}/avd-vaapi
chmod 755 %{buildroot}%{_bindir}/avd-vaapi

%check
%meson_test --num-processes 4

%files
%license COPYING
%dir %{_libdir}/aurora-avd
%dir %{_libdir}/aurora-avd/va
%{_libdir}/aurora-avd/va/v4l2_request_drv_video.so
%{_bindir}/avd-vaapi

%changelog
* Sun Nov 01 2026 Aurora contributors <noreply@aurora-silicon.org> - 1.3.r11-3
- Prime allocation/release paths before the resource fixture baseline

* Sun Nov 01 2026 Aurora contributors <noreply@aurora-silicon.org> - 1.3.r11-2
- Make offline test fixtures deterministic and recognize complete GCC startup diagnostics

* Sat Oct 31 2026 Aurora contributors <noreply@aurora-silicon.org> - 1.3.r11-1
- Pin the AVD bridge with a private application-scoped launcher
