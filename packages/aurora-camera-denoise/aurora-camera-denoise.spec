%global commit 456c567527d6bbba27d0aaeec1199032e0ec88c3
Name: aurora-camera-denoise
Version: 0.1.0
Release: 5%{?dist}
Summary: Noise filter for the built-in camera on Apple silicon
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
of the built-in camera on Apple silicon laptops, the way macOS does. For each
built-in camera it adds a camera node with the same name and formats; apps
pick it by default, and the original stays available. A temporal noise
filter runs on every frame, and a low-light stage (a backend plugin such as
the Neural Engine one) joins in above per-board sensor gain levels from
boards.conf. Users can turn it off in denoise.conf or mask the service.

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
# On for every user, like the camera filtering on macOS.
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
* Fri Nov 06 2026 Aurora Silicon <ryan@aurorasilicon.org> - 0.1.0-5
- Publish only formats the filter can fill: DMA-BUF-preferring clients
  (browsers, zero-copy players) now get a picture (camera-denoise#7).
- Update to 456c567527d6, which also brings the optional Vulkan temporal
  backend (CPU stays the default).

* Mon Nov 02 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-4
- Update to a929985764bc: when another program holds the camera, the filter
  now retries until it is free instead of giving apps a black picture.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-3
- Update to 77e35ccbfd2f: in low light the camera may slow below 30 fps so
  each frame gets more exposure, as macOS does. Turn it off with
  low-light-frame-rate = off in denoise.conf.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-2
- Update to da883730b16d: the temporal filter runs on every stream, as on
  macOS, with the low-light stage on top above the board's gain levels.

* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-1
- Initial Fedora Aurora package of camera-denoise 0.1.0 (846646456ee1),
  with the CPU backend. The user service is preset on.
