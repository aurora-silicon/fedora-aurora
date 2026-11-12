# Aurora's Mesa for Flatpak apps.
#
# Flatpak apps load OpenGL and Vulkan from the runtime's GL extension, not from
# the system, so without this they run Flathub's GL.default Mesa. This package
# carries org.freedesktop.Platform.GL.aurora (built by build-extension.sh
# from the same Mesa commit as mesa-aurora) as a local OSTree repository,
# installs it into the system Flatpak installation and enables it ahead of
# GL.default. Removing the package removes the extension and the settings, and
# apps go back to GL.default.
#
# Keep commit, Version and Release identical to packages/mesa-aurora, as for
# mesa-aurora-fex-guest: the tracker moves all three together and
# tests/test_specs.py checks it. A host Mesa built from another recipe can be
# matched without editing this file, e.g. for the fleet's mesa.spec line:
#   rpmbuild --define 'commit <40-hex>' --define 'host_version 26.3.0~devel' \
#            --define 'host_release 0.17.aurora.borealis.<12-hex>%%{?dist}' ...
#
# Source10 is mandatory. scripts/build-rpm builds it for both supported
# runtimes (or consumes AURORA_FLATPAK_GL_REPO_TAR). Never publish settings alone.
%{!?commit:%global commit 33cf8cfc66830cb093e3a35c024b92d1b01a9773}
%{!?host_version:%global host_version 26.3.0}
%{!?host_release:%global host_release 24%{?dist}.aurora}
%global shortcommit %{sub %{commit} 1 12}
%global debug_package %{nil}
%global __requires_exclude_from ^%{_datadir}/aurora-flatpak-gl/
%global __provides_exclude_from ^%{_datadir}/aurora-flatpak-gl/
Name: aurora-flatpak-gl
Version: %{host_version}
Release: %{host_release}
Summary: Aurora Mesa for Flatpak apps
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
Source0: aurora-flatpak-gl
Source1: 60-aurora-flatpak-gl.conf
Source2: aurora-flatpak-gl.sh
Source3: validate-repo.py
Source10: aurora-flatpak-gl-repo-%{shortcommit}.tar
ExclusiveArch: aarch64
BuildRequires: python3 ostree
Requires: flatpak

%description
Installs org.freedesktop.Platform.GL.aurora, Aurora's Mesa built for the
Freedesktop Flatpak runtimes, and enables it for every Flatpak app ahead of
Flathub's GL.default. Apps then get the same Asahi Gallium and Honeykrisp
drivers as the rest of the system. Runtime branches without a GL.aurora build
keep using GL.default.

%prep

%build

%install
install -Dm755 %{SOURCE0} %{buildroot}%{_libexecdir}/aurora-flatpak-gl/aurora-flatpak-gl
install -Dm644 %{SOURCE1} %{buildroot}%{_prefix}/lib/environment.d/60-aurora-flatpak-gl.conf
install -Dm644 %{SOURCE2} %{buildroot}%{_sysconfdir}/profile.d/aurora-flatpak-gl.sh
install -d %{buildroot}%{_datadir}/aurora-flatpak-gl
tar -xf %{SOURCE10} -C %{buildroot}%{_datadir}/aurora-flatpak-gl
repo=%{buildroot}%{_datadir}/aurora-flatpak-gl/repo
test -d $repo/objects
stamps=$(ls $repo/aurora-mesa-commit.* 2>/dev/null) || { echo 'repository has no Mesa commit stamp' >&2; exit 1; }
for s in $stamps; do
    [ "$(cat $s)" = %{commit} ] || { echo "$s is $(cat $s), not %{commit}" >&2; exit 1; }
done
python3 %{SOURCE3} "$repo" %{commit} 25.08 26.08

%posttrans
%{_libexecdir}/aurora-flatpak-gl/aurora-flatpak-gl enable >/dev/null || :

%preun
if [ $1 -eq 0 ]; then
    %{_libexecdir}/aurora-flatpak-gl/aurora-flatpak-gl disable >/dev/null || :
fi

%files
%{_libexecdir}/aurora-flatpak-gl/
%{_prefix}/lib/environment.d/60-aurora-flatpak-gl.conf
%config(noreplace) %{_sysconfdir}/profile.d/aurora-flatpak-gl.sh
%{_datadir}/aurora-flatpak-gl/

%changelog
* Thu Nov 12 2026 Aurora Silicon <ryan@aurorasilicon.org> - 26.3.0-24
- Track aurora-silicon/mesa aurora-wip at 33cf8cfc: GL stages writes to
  busy buffers and copies them on the GPU instead of waiting for the GPU
  (mesa#254, the Minecraft GL stutter), M5-family uniform ranges laid out
  in dwords so the native fragment program builder takes every GL draw
  (mesa#256), M5 G17G submission and CPU-path fixes (mesa#207, mesa#219),
  G17P stage uniforms, layered RGBA8 renders, state-0 images and mesh
  shaders (mesa#215, mesa#210, mesa#224, mesa#223), AGX3 packer fixes
  (mesa#230, mesa#216), Honeykrisp fragment shader interlock (mesa#226),
  coherent images on multi-cluster G13/G14 (mesa#247), resumed render pass
  ordering (mesa#249) and kills with subgroup ops (mesa#245).

* Thu Nov 12 2026 Aurora Silicon <ryan@aurorasilicon.org> - 26.3.0-23
- Track aurora-silicon/mesa aurora-wip at be147e36: transform feedback
  keeps a captured point size (mesa#211), revert of the varying
  optimisation that broke fast-linked pipeline libraries with viewport
  arrays (mesa#212), no signext optimisation over an abs source in the
  AGX compiler (mesa#232, OpenCL 64-bit multiplies).

* Wed Nov 11 2026 Aurora Silicon <ryan@aurorasilicon.org> - 26.3.0-22
- Track aurora-silicon/mesa aurora-wip at 7f7a7ffa: G13/G14 buffer device
  address capture/replay (mesa#222), G13/G14 sparse texel buffer residency
  and strict residency for vkd3d-proton only (mesa#235), divergent subgroup
  shuffles in vertex shaders (mesa#234), G17 occlusion query results with
  wait and no colour attachments (mesa#233), AGX3 uniform TCS image atomics
  (mesa#213), ray tracing hit-object parser tests (mesa#220).

* Wed Nov 11 2026 Aurora Silicon <ryan@aurorasilicon.org> - 26.3.0-21
- Track aurora-silicon/mesa aurora-wip at 10161a78: shader constant order
  independent of the build host and 32-bit unit tests fixed (mesa#209),
  native Gallium GL on the M5 Pro and M5 Max with CPU maps waiting for
  writers on other contexts (mesa#194), G17G perspective varyings (mesa#208),
  M5 Max admission and G17P/M5 fixes (mesa#195 #202-#206, #157, #125).

* Tue Nov 10 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-20
- Track aurora-silicon/mesa aurora-wip at 51b0b650: render ray-query scratch
  only on queues that use it (mesa#200), diagnostic environment switches read
  once (mesa#201), G17P end-only timestamps, small uploads, rematerialised
  preamble steps, 4-texel image-to-buffer copies and command memory retirement.
- Keep native, FEX guest and Flatpak Mesa sources and releases coordinated.

* Thu Nov 05 2026 Michal S. <michal_stopyra@icloud.com> - 26.3.0-19
- Include the merged Wayland drawable lifetime fix and unmatched-release
  handling (mesa#138).
- Keep native, FEX guest and Flatpak Mesa sources and releases coordinated.

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-16.aurora
- Move in lockstep with mesa-aurora 26.3.0-16.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-15.aurora
- Move in lockstep with mesa-aurora 26.3.0-15.

* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.3.0-14.aurora
- Move in lockstep with mesa-aurora 26.3.0-14.

* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.3.0-13.aurora
- Move in lockstep with mesa-aurora 26.3.0-13.

* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.3.0-12.aurora
- Move in lockstep with mesa-aurora 26.3.0-12.

* Sat Oct 31 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-11.aurora
- Require complete, validated GL payloads for both runtime branches.

* Thu Oct 29 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.3.0-7.aurora
- Move in lockstep with mesa-aurora: commit, Version and Release follow its
  pin, and the build checks the repository's Mesa commit stamps.
* Thu Oct 29 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-0.1.473e325b4f50
- Initial package: GL.aurora for the 25.08 and 26.08 runtimes from Mesa
  473e325b4f50.
