#!/usr/bin/env bash
# Stage the pinned signed ARM64 Neptune WDDM package published by UTM's
# guest-driver project. Authenticode verification still runs on Windows via
# verify-guest-driver.ps1; this script only downloads, hashes, and extracts.
set -euo pipefail

version=${AURORA_VIOGPU3D_VERSION:-v0.5}
url=${AURORA_VIOGPU3D_URL:-https://github.com/osy/kvm-guest-drivers-windows/releases/download/${version}/viogpu3d-arm64x-signed.zip}
expected=${AURORA_VIOGPU3D_SHA256:-155695ab7820f71e75c369aeae7b8c060691ba43646ac37edef72aa2428506d5}
destination=

usage() {
  cat <<'USAGE'
Usage: fetch-guest-driver.sh --destination PATH

Downloads the pinned ARM64X viogpu3d Neptune package and extracts its driver
files into PATH. Run verify-guest-driver.ps1 on Windows before using the
directory with aurora-windows-vm; this script does not claim Authenticode
verification.
USAGE
}

while (($#)); do
  case $1 in
    --destination) [[ $# -ge 2 ]] || { echo '--destination needs a path' >&2; exit 2; }; destination=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ -n $destination ]] || { echo '--destination is required' >&2; exit 2; }
command -v curl >/dev/null 2>&1 || { echo 'curl is required' >&2; exit 1; }
command -v unzip >/dev/null 2>&1 || { echo 'unzip is required' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo 'sha256sum is required' >&2; exit 1; }

mkdir -p "$destination"
tmp=$(mktemp "${TMPDIR:-/tmp}/aurora-viogpu3d.XXXXXX.zip")
stage=
cleanup() { rm -rf "$stage" "$tmp"; }
trap cleanup EXIT
curl --fail --location --retry 2 --proto '=https' --tlsv1.2 -o "$tmp" "$url"
actual=$(sha256sum "$tmp" | awk '{print $1}')
[[ $actual == "$expected" ]] || {
  echo "guest driver archive hash mismatch: expected $expected, got $actual" >&2
  exit 1
}

stage=$(mktemp -d "${TMPDIR:-/tmp}/aurora-viogpu3d.XXXXXX")
unzip -q "$tmp" 'drivers/viogpu3d/*' -d "$stage"
source="$stage/drivers/viogpu3d"
for required in viogpu3d.sys viogpu3d.inf viogpu3d.cat neptune_umd.dll \
                vulkan_virtio.dll virtio_icd.json; do
  [[ -f $source/$required ]] || { echo "archive is missing $required" >&2; exit 1; }
done
if command -v file >/dev/null 2>&1; then
  file "$source/viogpu3d.sys" | grep -Eiq 'aarch64|arm64' || {
    echo 'downloaded viogpu3d.sys is not an ARM64 PE image' >&2; exit 1;
  }
fi
cp -a "$source"/. "$destination"/
printf 'Staged viogpu3d %s at %s\n' "$version" "$destination"
printf 'Run verify-guest-driver.ps1 on Windows to create driver-signature.txt before launching.\n'
