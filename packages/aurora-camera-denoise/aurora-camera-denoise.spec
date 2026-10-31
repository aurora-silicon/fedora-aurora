%global commit 846646456ee17ba1fb60be169abcd0727bed36f4
Name: aurora-camera-denoise
Version: 0.1.0
Release: 2%{?dist}
Summary: Low-light denoise filter for the built-in camera on Apple silicon
License: MIT
URL: https://github.com/aurora-silicon/camera-denoise
Source0: https://github.com/aurora-silicon/camera-denoise/archive/%{commit}/%{name}-%{commit}.tar.gz
Source1: 80-aurora-camera-denoise.preset
ExclusiveArch: aarch64
BuildRequires: gcc meson ninja-build pkgconf-pkg-config systemd-rpm-macros
BuildRequires: pkgconfig(libpipewire-0.3) >= 1.0
BuildRequires: pkgconfig(systemd)
Requires: pipewire

%description
A PipeWire video filter that runs as a user service and takes the grain out
of the built-in camera on Apple silicon laptops in low light. When explicitly started, it adds a filtered camera node beside the original. It filters only on
boards with data in boards.conf (keyed by the device-tree compatible) unless
told otherwise, and follows the sensor gain the camera driver reports, or
the measured noise on kernels without that report.

%prep
%autosetup -n camera-denoise-%{commit}

%build
%meson -Ddaemon=enabled -Dsystemduserunitdir=%{_userunitdir}
%meson_build

%check
%meson_test

%install
%meson_install
# Backends other than the built-in CPU one are shared objects loaded from here.
install -d %{buildroot}%{_libdir}/aurora-camera-denoise
# The filter is opt-in; presets must never activate it on installation.
install -Dm644 %{SOURCE1} %{buildroot}%{_userpresetdir}/80-aurora-camera-denoise.preset

%post
%systemd_user_post aurora-camera-denoise.service
%preun
%systemd_user_preun aurora-camera-denoise.service
%postun
%systemd_user_postun_with_restart aurora-camera-denoise.service

%files
%license LICENSE
%doc README.md docs/
%{_bindir}/aurora-camera-denoise
%{_bindir}/aurora-camera-denoise-bench
%{_bindir}/aurora-camera-denoise-metrics
%{_datadir}/aurora-camera-denoise/
%dir %{_libdir}/aurora-camera-denoise
%{_userunitdir}/aurora-camera-denoise.service
%{_userpresetdir}/80-aurora-camera-denoise.preset

%changelog
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-2
- Keep camera effects opt-in.

* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-1
- Initial Fedora Aurora package of camera-denoise 0.1.0 (846646456ee1),
  with the CPU backend. The user service is available but disabled by default.
