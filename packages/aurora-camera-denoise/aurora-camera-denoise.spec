%global commit 74bb45ab9946634668bac3e2a8c655a5e81fd7b9
Name: aurora-camera-denoise
Version: 0.1.0
Release: 8%{?dist}
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
%autosetup -p1 -n camera-denoise-%{commit}

%build
%meson -Ddaemon=enabled -Dgpu=disabled -Dsystemduserunitdir=%{_userunitdir}
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
%{_bindir}/aurora-camera-denoise-compare
%{_bindir}/aurora-camera-denoise-metrics
%{_datadir}/aurora-camera-denoise/
%dir %{_libdir}/aurora-camera-denoise
%{_libdir}/aurora-camera-denoise/cdn-backend-ave.so
%{_libdir}/aurora-camera-denoise/cdn-backend-ane.so
%{_userunitdir}/aurora-camera-denoise.service
%{_userpresetdir}/80-aurora-camera-denoise.preset

%changelog
* Wed Nov 11 2026 Aurora Silicon <ryan@aurorasilicon.org> - 0.1.0-8
- Update to 74bb45ab9946: add the Neural Engine low-light stage
  (cdn-backend-ane.so, camera-denoise#11). In low light a small open CNN
  runs on top of the temporal filter, built by our ANE compiler for the
  M4 Pro (H16G) at 1080p; other Macs keep the temporal filter alone.

* Wed Nov 11 2026 Aurora Silicon <ryan@aurorasilicon.org> - 0.1.0-7
- Update to 4a2d2402d991. The temporal filter now runs by default on the
  video encoder's motion-compensated filter, the hardware macOS uses, when
  the kernel has its device and the scaler's lossless form (camera-denoise#9,
  #10). Its output matches macOS, and on the MacBook Neo it takes 4% of one
  core at 30 fps where the CPU filter takes 39%. Other kernels keep the CPU
  filter. The plugin is cdn-backend-ave.so.
- Also brings opt-in camera effects controls (camera-denoise#2, #3, #4, #6).
- camera-denoise#8 is upstream now; drop its patch.

* Tue Nov 10 2026 Aurora Silicon <ryan@aurorasilicon.org> - 0.1.0-6
- The user service no longer runs in root's or the greeter's user manager,
  where it failed every 2 s without a PipeWire session, and it stops after
  5 failures in a minute (camera-denoise#8).

* Fri Nov 06 2026 Aurora Silicon <ryan@aurorasilicon.org> - 0.1.0-5
- Publish only formats the filter can fill: DMA-BUF-preferring clients
  (browsers, zero-copy players) now get a picture (camera-denoise#7).
- Update to 456c567527d6, which also brings the optional Vulkan temporal
  backend, left out of this package (-Dgpu=disabled); CPU is the default.

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
