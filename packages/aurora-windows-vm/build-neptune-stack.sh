#!/usr/bin/env bash
# Build the Linux host half of UTM's Windows Neptune/Venus graphics path.
# This deliberately does not build the Windows WDDM package: that requires a
# Windows WDK/MSVC environment (see README.md).
set -euo pipefail

QEMU_URL=${AURORA_UTM_QEMU_URL:-https://github.com/utmapp/qemu.git}
QEMU_COMMIT=${AURORA_UTM_QEMU_COMMIT:-2934963d1778e4d74ac2f667820cf81c914ff0f5}
VIRGL_URL=${AURORA_UTM_VIRGL_URL:-https://github.com/utmapp/virglrenderer.git}
VIRGL_COMMIT=${AURORA_UTM_VIRGL_COMMIT:-cf5af71359b224a9a482e9b5a67f8160497dc951}
DXVK_URL=${AURORA_UTM_DXVK_URL:-https://github.com/osy/dxvk.git}
DXVK_COMMIT=${AURORA_UTM_DXVK_COMMIT:-389d26b360b0080f4ffe816779960745434aef6a}
VKD3D_URL=${AURORA_UTM_VKD3D_URL:-https://github.com/osy/vkd3d-proton.git}
VKD3D_COMMIT=${AURORA_UTM_VKD3D_COMMIT:-a8b7cd423d85ff2759a395fd12aae9f0bf123dcc}
DIRECTX_NATIVE_URL=${AURORA_UTM_DIRECTX_NATIVE_URL:-https://github.com/osy/directx-native.git}
DIRECTX_NATIVE_COMMIT=${AURORA_UTM_DIRECTX_NATIVE_COMMIT:-7258be1c56cdbf1e55c56b1bc4a866169c8ca0da}

root=${AURORA_NEPTUNE_ROOT:-$PWD/.aurora-neptune}
prefix=${AURORA_NEPTUNE_PREFIX:-$root/prefix}
qemu_src=$root/qemu
virgl_src=$root/virglrenderer
dxvk_src=$root/dxvk
dxvk_build=$root/dxvk-build
vkd3d_src=$root/vkd3d-proton
vkd3d_build=$root/vkd3d-build
directx_native_src=$root/directx-native
qemu_build=$root/qemu-build
virgl_build=$root/virglrenderer-build
configure_only=0
skip_qemu=0
build_dxvk=1
offline=${AURORA_NEPTUNE_OFFLINE:-0}
prefix_explicit=0
[[ -n ${AURORA_NEPTUNE_PREFIX:-} ]] && prefix_explicit=1
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
virgl_patch=${AURORA_UTM_VIRGL_PATCH:-$script_dir/patches/0001-neptune-directx-native-abi.patch}

usage() {
  cat <<'USAGE'
Usage: build-neptune-stack.sh [options]

Builds UTM's Linux Neptune host stack at pinned commits. The output prefix
contains virglrenderer and a QEMU aarch64 binary. It requires Linux build
prerequisites, a Vulkan-capable D3D12 backend (DXVK/vkd3d-proton), Meson and
Ninja. The Windows WDDM guest driver is built separately on Windows with the
WDK; this script never pretends to produce it.

Options:
  --root PATH       source/build root (default: ./.aurora-neptune)
  --prefix PATH     install prefix (default: ROOT/prefix)
  --configure-only  clone and configure, but do not compile
  --skip-qemu       build virglrenderer only
  --no-dxvk         require an already installed dxvk-dxgi.pc
  -h, --help        show this help

Environment:
  AURORA_WIDL_PATH  standalone Wine widl executable for the vkd3d build
  AURORA_WINE_SOURCE  Wine source tree containing tools/widl/widl
USAGE
}
while (($#)); do
  case $1 in
    --root) [[ $# -ge 2 ]] || { echo '--root needs a path' >&2; exit 2; }; root=$2; shift 2 ;;
    --prefix) [[ $# -ge 2 ]] || { echo '--prefix needs a path' >&2; exit 2; }; prefix=$2; prefix_explicit=1; shift 2 ;;
    --configure-only) configure_only=1; shift ;;
    --skip-qemu) skip_qemu=1; shift ;;
    --no-dxvk) build_dxvk=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
if (( ! prefix_explicit )); then
  prefix=$root/prefix
fi
mkdir -p "$root"
root=$(CDPATH= cd -- "$root" && pwd)
if (( prefix_explicit )); then
  prefix_dir=$(dirname -- "$prefix")
  mkdir -p "$prefix_dir"
  prefix="$(CDPATH= cd -- "$prefix_dir" && pwd)/$(basename -- "$prefix")"
else
  prefix=$root/prefix
fi
qemu_src=$root/qemu
virgl_src=$root/virglrenderer
dxvk_src=$root/dxvk
dxvk_build=$root/dxvk-build
vkd3d_src=$root/vkd3d-proton
vkd3d_build=$root/vkd3d-build
directx_native_src=$root/directx-native
qemu_build=$root/qemu-build
virgl_build=$root/virglrenderer-build
mkdir -p "$prefix"

# A source override is useful for an audited offline build (and avoids
# silently substituting a moving checkout for the pinned revision).
if [[ -n ${AURORA_UTM_DXVK_SOURCE:-} ]]; then dxvk_src=$AURORA_UTM_DXVK_SOURCE; fi
if [[ -n ${AURORA_UTM_VKD3D_SOURCE:-} ]]; then vkd3d_src=$AURORA_UTM_VKD3D_SOURCE; fi
if [[ -n ${AURORA_UTM_VIRGL_SOURCE:-} ]]; then virgl_src=$AURORA_UTM_VIRGL_SOURCE; fi
if [[ -n ${AURORA_UTM_QEMU_SOURCE:-} ]]; then qemu_src=$AURORA_UTM_QEMU_SOURCE; fi
if [[ -n ${AURORA_UTM_DIRECTX_NATIVE_SOURCE:-} ]]; then directx_native_src=$AURORA_UTM_DIRECTX_NATIVE_SOURCE; fi

command -v meson >/dev/null 2>&1 || { echo 'meson is required' >&2; exit 1; }
command -v ninja >/dev/null 2>&1 || { echo 'ninja is required' >&2; exit 1; }
command -v pkg-config >/dev/null 2>&1 || { echo 'pkg-config is required' >&2; exit 1; }
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig:$prefix/lib64/pkgconfig:${PKG_CONFIG_PATH:-}"

clone_at() {
  local url=$1 commit=$2 dst=$3
  if [[ ! -d $dst/.git ]]; then
    (( offline )) && { echo "offline source missing: $dst" >&2; exit 1; }
    git clone --filter=blob:none --recurse-submodules "$url" "$dst"
  fi
  if [[ $(git -C "$dst" rev-parse HEAD 2>/dev/null || true) != "$commit" ]]; then
    (( offline )) && { echo "offline source has wrong revision: $dst" >&2; exit 1; }
    git -C "$dst" fetch --no-tags --depth=1 origin "$commit"
    git -C "$dst" checkout --detach --force "$commit"
  fi
  [[ $(git -C "$dst" rev-parse HEAD) == "$commit" ]] || {
    echo "source verification failed for $dst" >&2; exit 1;
  }
  if [[ -f $dst/.gitmodules ]]; then
    git -C "$dst" submodule update --init --recursive
  fi
}

verify_source() {
  local dst=$1 commit=$2
  [[ -d $dst/.git ]] || { echo "source missing: $dst" >&2; exit 1; }
  [[ $(git -C "$dst" rev-parse HEAD) == "$commit" ]] || {
    echo "source verification failed for $dst (expected $commit)" >&2; exit 1;
  }
}

# vkd3d-proton consumes directx-native as a Meson subproject.  Its wrap file
# would otherwise try to access GitHub during an offline build, and a symlink
# is not sufficient because Meson needs to create its own subproject metadata
# next to the source.  Stage a real copy before vkd3d's Meson setup.
prepare_vkd3d_directx_native() {
  local source=$dxvk_src/subprojects/directx-native
  local destination=$vkd3d_src/subprojects/directx-native

  if [[ ! -f $source/meson.build ]]; then
    source=$directx_native_src
    if [[ -n ${AURORA_UTM_DIRECTX_NATIVE_SOURCE:-} ]]; then
      verify_source "$source" "$DIRECTX_NATIVE_COMMIT"
    else
      clone_at "$DIRECTX_NATIVE_URL" "$DIRECTX_NATIVE_COMMIT" "$source"
    fi
  fi
  [[ -f $source/meson.build ]] || {
    echo "directx-native Meson source missing: $source" >&2; exit 1;
  }

  # Keep an already-staged real checkout/copy.  Replace stale symlinks (from
  # older builder revisions) and incomplete directories deterministically.
  if [[ -L $destination || ! -f $destination/meson.build ]]; then
    rm -rf "$destination"
    mkdir -p "$(dirname -- "$destination")"
    cp -a "$source" "$destination"
  fi
  [[ ! -L $destination && -f $destination/meson.build ]] || {
    echo "failed to stage directx-native for vkd3d: $destination" >&2; exit 1;
  }
}

if ! pkg-config --exists dxvk-dxgi; then
  if (( ! build_dxvk )); then
    echo 'dxvk-dxgi.pc is missing; install/build the UTM DXVK fork with shared-resource descriptors first.' >&2
    echo 'Neptune cannot be built without this ABI.' >&2
    exit 1
  fi
  if [[ -n ${AURORA_UTM_DXVK_SOURCE:-} ]]; then verify_source "$dxvk_src" "$DXVK_COMMIT"; else clone_at "$DXVK_URL" "$DXVK_COMMIT" "$dxvk_src"; fi
  if (( configure_only )); then
    echo 'dxvk-dxgi.pc is missing; configure-only cannot proceed without an installed DXVK host ABI.' >&2
    echo 'Run without --configure-only to build the pinned DXVK fork.' >&2
    exit 1
  fi
  if [[ ! -f $dxvk_build/build.ninja ]]; then
    meson setup "$dxvk_build" "$dxvk_src" \
      --prefix "$prefix" --buildtype=release \
      -Dnative_headless=true \
      -Denable_dxgi=true -Denable_d3d11=true \
      -Denable_d3d8=false -Denable_d3d9=false -Denable_d3d10=false
  fi
  ninja -C "$dxvk_build" install

fi

dxvk_libdir="$prefix/lib"
if [[ ! -f "$dxvk_libdir/libdxvk_d3d11.so" || ! -f "$dxvk_libdir/libdxvk_dxgi.so" ]]; then
  pkg_libdir=$(pkg-config --variable=libdir dxvk-d3d11 2>/dev/null || true)
  [[ -n $pkg_libdir ]] && dxvk_libdir=$pkg_libdir
fi
dxvk_d3d11_lib="$dxvk_libdir/libdxvk_d3d11.so"
dxvk_dxgi_lib="$dxvk_libdir/libdxvk_dxgi.so"
[[ -f "$dxvk_d3d11_lib" && -f "$dxvk_dxgi_lib" ]] || {
  echo "DXVK native libraries are missing from the build prefix: $prefix/lib" >&2
  exit 1
}
if ! nm -D "$dxvk_d3d11_lib" 2>/dev/null | grep -Eq '[[:space:]]dxvk_d3d11_buffer_bind_external_fd$'; then
  echo "DXVK D3D11 backend lacks the directx-native external-fd entry point" >&2
  exit 1
fi
if ! nm -D "$dxvk_d3d11_lib" 2>/dev/null | grep -Eq '[[:space:]]D3D11CreateDevice$' ||
   ! nm -D "$dxvk_dxgi_lib" 2>/dev/null | grep -Eq '[[:space:]]CreateDXGIFactory1$'; then
  echo "DXVK host libraries lack the required D3D11/DXGI entry points" >&2
  exit 1
fi

# Neptune's D3D12 entry points and dmabuf heap importer come from the pinned
# native vkd3d-proton fork. Building only DXVK would leave D3D11 available
# while every D3D12CreateDevice call fails in the render worker.
if [[ ! -f "$prefix/lib/libvkd3d-proton-d3d12.so" ]]; then
  if [[ -n ${AURORA_UTM_VKD3D_SOURCE:-} ]]; then
    verify_source "$vkd3d_src" "$VKD3D_COMMIT"
  else
    clone_at "$VKD3D_URL" "$VKD3D_COMMIT" "$vkd3d_src"
  fi
  prepare_vkd3d_directx_native
fi
vkd3d_lib="$prefix/lib/libvkd3d-proton-d3d12.so"
if [[ ! -f "$vkd3d_lib" ]]; then
  if (( configure_only )); then
    echo 'libvkd3d-proton-d3d12.so is missing; configure-only cannot produce the D3D12 host backend.' >&2
    exit 1
  fi
  # A full Wine package is not required just to generate vkd3d's IDL
  # wrappers.  Permit an explicitly supplied standalone widl, or the
  # already-built Wine source tool in an offline build root.  This keeps the
  # managed build guest independent of pacman while still failing closed when
  # no real widl executable is available.
  widl_bin=${AURORA_WIDL_PATH:-}
  if [[ -n $widl_bin ]]; then
    [[ -x $widl_bin ]] || {
      echo "AURORA_WIDL_PATH is not executable: $widl_bin" >&2; exit 1;
    }
  else
    widl_bin=$(command -v widl || true)
    if [[ -z $widl_bin ]]; then
      for widl_candidate in \
        "${AURORA_WINE_SOURCE:-}/tools/widl/widl" \
        "${AURORA_UTM_WINE_SOURCE:-}/tools/widl/widl" \
        "$PWD/.aurora-wine-source/tools/widl/widl" \
        "$root/wine/tools/widl/widl"; do
        if [[ -n $widl_candidate && -x $widl_candidate ]]; then
          widl_bin=$widl_candidate
          break
        fi
      done
    fi
  fi
  [[ -n $widl_bin && -x $widl_bin ]] || {
    echo 'widl is required to build the native vkd3d-proton D3D12 backend.' >&2
    echo 'Install Wine widl or set AURORA_WIDL_PATH to a standalone widl binary.' >&2
    exit 1
  }
  # vkd3d's Meson files invoke the tool by basename.
  widl_bin_dir=$(CDPATH= cd -- "$(dirname -- "$widl_bin")" && pwd)
  export PATH="$widl_bin_dir:$PATH"
  command -v widl >/dev/null 2>&1 || {
    echo "widl could not be placed on PATH: $widl_bin" >&2; exit 1;
  }
  command -v glslangValidator >/dev/null 2>&1 || command -v glslang >/dev/null 2>&1 || {
    echo 'glslangValidator (or glslang) is required to build vkd3d-proton.' >&2
    exit 1
  }
  if [[ ! -f "$vkd3d_build/build.ninja" ]]; then
    meson setup "$vkd3d_build" "$vkd3d_src" \
      --prefix "$prefix" --buildtype=release \
      -Denable_tests=false -Denable_extras=false
  fi
  ninja -C "$vkd3d_build" install
fi
[[ -f "$vkd3d_lib" ]] || {
  echo "vkd3d-proton build did not install $vkd3d_lib" >&2
  exit 1
}
if ! nm -D "$vkd3d_lib" 2>/dev/null | grep -Eq '[[:space:]]D3D12CreateDevice$'; then
  echo "vkd3d-proton backend does not export D3D12CreateDevice: $vkd3d_lib" >&2
  exit 1
fi

# Neptune and the UTM DXVK fork share a headers-only descriptor ABI. Prefer
# the headers from the verified DXVK checkout; a preinstalled host stack may
# provide the same ABI through pkg-config instead.
if [[ -d $dxvk_src/subprojects/directx-native/include/directx-native ]]; then
  dxn_include=$dxvk_src/subprojects/directx-native/include/directx-native
  mkdir -p "$prefix/include/directx-native" "$prefix/lib/pkgconfig"
  cp -a "$dxn_include"/. "$prefix/include/directx-native/"
  cat > "$prefix/lib/pkgconfig/directx-native-headers.pc" <<PC
prefix=$prefix
exec_prefix=\${prefix}
includedir=\${prefix}/include
Name: directx-native-headers
Description: directx-native shared descriptor ABI headers
Version: 0.1
Cflags: -I\${includedir}
PC
elif ! pkg-config --exists directx-native-headers; then
  if [[ -n ${AURORA_UTM_DIRECTX_NATIVE_SOURCE:-} ]]; then
    verify_source "$directx_native_src" "$DIRECTX_NATIVE_COMMIT"
  else
    clone_at "$DIRECTX_NATIVE_URL" "$DIRECTX_NATIVE_COMMIT" "$directx_native_src"
  fi
  [[ -d "$directx_native_src/include/directx-native" ]] || {
    echo "directx-native headers missing: $directx_native_src" >&2; exit 1;
  }
  mkdir -p "$prefix/include/directx-native" "$prefix/lib/pkgconfig"
  cp -a "$directx_native_src/include/directx-native"/. "$prefix/include/directx-native/"
  cat > "$prefix/lib/pkgconfig/directx-native-headers.pc" <<PC
prefix=$prefix
exec_prefix=\${prefix}
includedir=\${prefix}/include
Name: directx-native-headers
Description: directx-native shared descriptor ABI headers
Version: 1.0.0
Cflags: -I\${includedir}
PC
fi

if [[ -n ${AURORA_UTM_VIRGL_SOURCE:-} ]]; then verify_source "$virgl_src" "$VIRGL_COMMIT"; else clone_at "$VIRGL_URL" "$VIRGL_COMMIT" "$virgl_src"; fi
if (( ! skip_qemu )); then
  if [[ -n ${AURORA_UTM_QEMU_SOURCE:-} ]]; then verify_source "$qemu_src" "$QEMU_COMMIT"; else clone_at "$QEMU_URL" "$QEMU_COMMIT" "$qemu_src"; fi
fi

[[ -f $virgl_patch ]] || {
  echo "virglrenderer DXVK ABI patch missing: $virgl_patch" >&2
  exit 1
}
virgl_patch_marker="$virgl_src/.aurora-directx-native-abi.patch.sha256"
virgl_patch_hash=$(sha256sum "$virgl_patch" | awk '{print $1}')
if [[ ! -f $virgl_patch_marker || $(cat "$virgl_patch_marker") != "$virgl_patch_hash" ]]; then
  if git -C "$virgl_src" apply --reverse --check "$virgl_patch" >/dev/null 2>&1; then
    : # already applied to this checkout
  elif git -C "$virgl_src" apply --check "$virgl_patch" >/dev/null 2>&1; then
    git -C "$virgl_src" apply "$virgl_patch"
  elif grep -q 'directx-native/dxn_shared.h' "$virgl_src/src/neptune/npt_shared.c" \
       && grep -q 'dxvk_d3d11_buffer_bind_external_fd' "$virgl_src/src/neptune/npt_library.c" \
       && [[ -f "$virgl_src/subprojects/directx-native.wrap" ]]; then
    echo 'virglrenderer already carries the directx-native ABI patch; recording its hash.'
  else
    echo "virglrenderer source has incompatible or unexpected local changes; refusing to apply $virgl_patch." >&2
    exit 1
  fi
  printf '%s\n' "$virgl_patch_hash" > "$virgl_patch_marker"
fi

# Avoid a Meson wrap download in the managed build guest.  The DXVK checkout
# already contains the exact directx-native revision used by its ABI; use that
# source as virglrenderer's fallback subproject.  A source override can supply
# a separate verified checkout when the DXVK tree is unavailable.
dxn_source=$dxvk_src/subprojects/directx-native
if [[ ! -f "$dxn_source/meson.build" ]]; then
  dxn_source=$directx_native_src
fi
[[ -f "$dxn_source/meson.build" ]] || {
  echo "directx-native Meson source missing: $dxn_source" >&2; exit 1;
}
if [[ ! -f "$virgl_src/subprojects/directx-native/meson.build" ]]; then
  rm -rf "$virgl_src/subprojects/directx-native"
  ln -s "$dxn_source" "$virgl_src/subprojects/directx-native"
fi

if [[ ! -f $virgl_build/build.ninja ]]; then
  meson setup "$virgl_build" "$virgl_src" \
    --prefix "$prefix" \
    -Dbuildtype=release -Db_ndebug=true \
    -Dplatforms=egl -Dvenus=true -Dneptune=true \
    -Dvulkan-dload=true -Dvulkan-preload=false \
    -Dtests=false
else
  meson configure "$virgl_build" --prefix "$prefix" \
    -Dvenus=true -Dneptune=true -Dplatforms=egl -Dtests=false
fi
if (( ! configure_only )); then
  ninja -C "$virgl_build" install
fi

if (( ! skip_qemu )); then
  export PKG_CONFIG_PATH="$prefix/lib/pkgconfig:$prefix/lib64/pkgconfig:${PKG_CONFIG_PATH:-}"
  if [[ ! -f $qemu_build/build.ninja ]]; then
    mkdir -p "$qemu_build"
    (cd "$qemu_build" && "$qemu_src/configure" \
      --target-list=aarch64-softmmu \
      --prefix="$prefix" \
      --enable-virglrenderer --disable-werror)
  fi
  if (( ! configure_only )); then
    ninja -C "$qemu_build" install
  fi
fi

if (( configure_only )); then
  echo "configured Neptune stack at $root (no compilation performed)"
  exit 0
fi

qemu=$prefix/bin/qemu-system-aarch64
[[ -x $qemu ]] || qemu=$(command -v qemu-system-aarch64 || true)
[[ -n $qemu && -x $qemu ]] || { echo 'built qemu-system-aarch64 not found' >&2; exit 1; }
help=$($qemu -device virtio-gpu-gl-pci,help 2>&1 || true)
printf '%s\n' "$help" | grep -q 'neptune' || {
  echo 'QEMU build does not expose virtio-gpu-gl-pci,neptune; refusing to call it accelerated.' >&2
  exit 1
}

cat > "$prefix/neptune-build-manifest.txt" <<MANIFEST
QEMU_URL=$QEMU_URL
QEMU_COMMIT=$QEMU_COMMIT
VIRGLRENDERER_URL=$VIRGL_URL
VIRGLRENDERER_COMMIT=$VIRGL_COMMIT
DXVK_URL=$DXVK_URL
DXVK_COMMIT=$DXVK_COMMIT
DXVK_D3D11=$dxvk_d3d11_lib
DXVK_DXGI=$dxvk_dxgi_lib
DIRECTX_NATIVE_URL=$DIRECTX_NATIVE_URL
DIRECTX_NATIVE_COMMIT=$DIRECTX_NATIVE_COMMIT
VKD3D_URL=$VKD3D_URL
VKD3D_COMMIT=$VKD3D_COMMIT
VKD3D_D3D12=$vkd3d_lib
QEMU=$qemu
PREFIX=$prefix
QEMU_DEVICE=virtio-gpu-gl-pci,hostmem=4G,blob=on,neptune=on
VIRGL_OPTIONS=-Dvenus=true -Dneptune=true
MANIFEST
printf 'Neptune host stack built and verified: %s\n' "$prefix/neptune-build-manifest.txt"
