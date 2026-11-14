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
%{!?commit:%global commit bbad52187b6086375806e2430f605fbe70c1c78d}
%{!?host_version:%global host_version 26.3.0}
%{!?host_release:%global host_release 28%{?dist}.aurora}
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
* Sat Nov 14 2026 Diljit Singh <hey@djdev.me> - 26.3.0-28
- Pin aurora-silicon/mesa aurora-wip bbad52187b6 (20 first-parent commits since f54acc022c8):
  - mesa#315 hk: mesh and task shaders by default on G17P
  - mesa#325 hk: advertise VK_EXT_nested_command_buffer on G17P
  - mesa#324 hk: VK_EXT_descriptor_buffer on G17P
  - mesa#323 hk: test that the vertex texture-heap shift keeps ray-query
    state in place
  - mesa#321 hk: dispatch ray tracing continuations through balanced
    searches
  - mesa#314 agx: end G17P ray-query compute kernels with the SCS sweep
  - mesa#310 hk: spread independent G17P compute submissions over sibling
    kernel queues
  - mesa#329 hk: restore the runtime's pipeline stage record after meta
  - mesa#322 hk: keep G17P ray-query state out of the vertex texture-heap
    shift
  - mesa#317 asahi: keep M5 tessellation on the CPU path when it can
    tessellate
  - mesa#318 asahi,hk: M5: one coverage update for per-sample kills
  - mesa#309 agx: flatten small uniform ifs that load, and issue M5 compute
    loads ahead of their uses
  - mesa#308 agx: retire pending loads at M5 workgroup barriers
  - mesa#316 agx: admit the M5 cube-array comparison with a per-lane level
  - mesa#301 hk: VK_EXT_primitives_generated_query on G17P
  - mesa#251 hk: raise the G18G compute batch default from 8 to 64
  - mesa#296 G17P: per-sample kills go into the one coverage update (killed
    samples keep their contents)
  - mesa#313 asahi: neutral wording for the AGX3 encoding-table comments
  - mesa#312 hk, agx: remove the M5 captured-runtime ray query route
  - mesa#297 agx: keep G18G per-lane levels and biases as 16-bit scalars
    (mpv scalers render solid blue on the M6)

* Fri Nov 13 2026 Aurora Silicon <ryan@aurorasilicon.org> - 26.3.0-27
- Track aurora-silicon/mesa aurora-wip at f54acc02: G17P no longer
  compresses storage images, which read back wrong texels when bound to
  reused memory (mesa#311), VK_NV_cooperative_matrix2 is advertised only
  on the M5 (mesa#304), the M5 programs custom primitive restart indices
  (mesa#307), stores through a linear window past its 3D store slice
  limit (mesa#303), page-aligns the layers of mipmapped writeable arrays
  (mesa#302) and keeps the VDM stream link context-relative, fixing a GPU
  fault with many small draws (mesa#276), the 8x8 cooperative matrix on
  AGX3B behind ASAHI_AGX3B_COOPERATIVE_MATRIX (mesa#275), and G18G CDM
  barriers (mesa#295).

* Fri Nov 13 2026 Aurora Silicon <ryan@aurorasilicon.org> - 26.3.0-26
- Track aurora-silicon/mesa aurora-wip at 5ccdc3f8: G17P tests a
  per-sample fragment's coverage once, fixing GPU stalls beside a
  second client (mesa#294), G17P admits queues before consuming
  submission payloads (mesa#293), the M5 draws GL tessellation natively
  (mesa#292), tiny positive LOD clamps stay above zero (mesa#289),
  VK_NV_cooperative_matrix2 on the M5 (mesa#244, mesa#246, mesa#291),
  VK_EXT_memory_priority and VK_EXT_pageable_device_local_memory
  (mesa#243), the hk_compute_timeout_ms option (mesa#259), G17P ray
  tracing with recursion depth 31, pipeline caching, more vertex
  formats, subgroups and faster opaque ray queries (mesa#270-mesa#274,
  mesa#278, mesa#286, mesa#288), batched and overlapped acceleration
  structure builds (mesa#283), M5 fixes for bfloat16 rounding,
  device-scope barriers, barrier memory scope, layered storage images,
  occlusion queries, empty compute work and command-memory reaping
  (mesa#264, mesa#266-mesa#269, mesa#277, mesa#284), a second compute
  queue on the M5 Max (mesa#260), earlier G13/G14 tiling overlap
  (mesa#265), fused fp32 ffma under DenormPreserve (mesa#280), shader
  object binaries independent of depthClipControl (mesa#279), the 10-bit
  X2 formats (mesa#282) and G17P staged renders (mesa#281).

* Fri Nov 13 2026 Aurora Silicon <ryan@aurorasilicon.org> - 26.3.0-25
- Track aurora-silicon/mesa aurora-wip at 8f013bf9: the M5 family caches
  its native graphics programs per linked shader (mesa#257), AGX3 keeps
  the move after a projective multiply, fixing G17S mediump varyings
  (mesa#258), G17P software tessellation stages batched per render
  (mesa#228), G17P depth clip control, restart state and storage image
  compression (mesa#225, mesa#227, mesa#253), single-level depth array
  compression on the M4 Pro (mesa#229), M5 compute: matrix multiply
  operands, instruction selection and dispatch overlap (mesa#238,
  mesa#239, mesa#240, mesa#241), VK_EXT_external_memory_host with
  GEM_USERPTR (mesa#242), cheaper signed-zero fmin/fmax (mesa#231), an
  i386 struct layout fix (mesa#214) and the Honeykrisp driver ID for ggml-
  vulkan (mesa#252).

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
