#!/bin/bash
# SPDX-License-Identifier: MIT
set -euo pipefail
ulimit -c 0
commit=${1:?public Mesa commit}
export TMPDIR=/r/tmp MESA_GIT_SHA1_OVERRIDE="$commit"
trap 'rc=$?; echo "$rc" > /r/out/build.rc' EXIT
test "$(uname -m)" = aarch64
cat /etc/fedora-release > /r/out/fedora-release.txt
dnf -y -q install rpm-build dnf5-plugins file zstd
D=(--define '_topdir /r/buildroot' --define '_sourcedir /r/SOURCES' --define '_smp_mflags -j4')
spec=/r/SPECS/mesa.spec
dnf -y -q builddep --setopt=install_weak_deps=False "${D[@]}" "$spec"
set +e
rpmbuild -br "${D[@]}" "$spec" > /r/out/buildrequires.log 2>&1
br=$?
set -e
test "$br" = 0 || test "$br" = 11
if compgen -G '/r/buildroot/SRPMS/*.buildreqs.nosrc.rpm' >/dev/null; then
  dnf -y -q builddep /r/buildroot/SRPMS/*.buildreqs.nosrc.rpm
fi
rpm -qa | sort > /r/out/buildroot-rpm-qa.txt

# Build fresh public sources, independently of RPM %prep's package patches.
python3 - "$commit" <<'PY'
import hashlib, json, pathlib, sys
manifest=json.loads(pathlib.Path('/r/out/source-manifest.json').read_text())
assert manifest['commit']==sys.argv[1] and manifest['kind']=='native'
for name, checksum in manifest['files'].items():
    path=pathlib.Path('/r')/name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==checksum, name
PY
mkdir /r/overlay-source /r/overlay-cargo
excludes=(--exclude=AGENTS.md --exclude='*/AGENTS.md'
  --exclude=CLAUDE.md --exclude='*/CLAUDE.md'
  --exclude=GEMINI.md --exclude='*/GEMINI.md'
  --exclude='*copilot-instructions*')
tar -xJf /r/SOURCES/mesa-26.3.0-devel.tar.xz -C /r/overlay-source --no-same-owner "${excludes[@]}"
src=/r/overlay-source/mesa-26.3.0-devel

# Reuse the recipe's checksum-pinned public Cargo inputs without downloads.
for crate in paste-1.0.15 proc-macro2-1.0.107 quote-1.0.47 rustc-hash-2.1.3 syn-2.0.119 unicode-ident-1.0.26; do
  tar -xzf "/r/SOURCES/$crate.tar.gz" -C /r/overlay-cargo --no-same-owner "${excludes[@]}"
done
python3 - "$src" <<'PY'
import pathlib, sys
source=pathlib.Path(sys.argv[1])
crates=[('paste',1,'1.0.15'),('proc-macro2',1,'1.0.107'),('quote',1,'1.0.47'),
        ('rustc-hash',2,'2.1.3'),('syn',2,'2.0.119'),('unicode-ident',1,'1.0.26')]
for name,major,version in crates:
    wrap=f'{name}-{major}-rs'
    path=source/'subprojects'/(wrap+'.wrap')
    assert path.is_file(), path
    path.write_text(f'[wrap-file]\ndirectory = {name}-{version}\npatch_directory = {wrap}\n')
PY
export MESON_PACKAGE_CACHE_DIR=/r/overlay-cargo
options=(--prefix=/usr --libdir=lib64 --buildtype=release --wrap-mode=nodownload
  -Db_ndebug=true -Dplatforms=x11,wayland -Dgallium-drivers=asahi,zink -Dvulkan-drivers=asahi
  -Dgallium-rusticl=false -Dgallium-va=disabled -Dbuild-tests=false
  -Degl=enabled -Dgbm=enabled -Dglx=dri -Dglvnd=enabled -Dgles1=enabled -Dgles2=enabled)
printf '%s\n' "${options[@]}" > /r/out/meson-options.txt
meson setup /r/overlay-tools "$src" "${options[@]}" -Dllvm=enabled -Dshared-llvm=enabled > /r/out/tools-setup.log 2>&1
ninja -C /r/overlay-tools -j4 src/compiler/clc/mesa_clc src/compiler/spirv/vtn_bindgen2 src/asahi/clc/asahi_clc > /r/out/tools-build.log 2>&1
cat > /r/overlay-tools.ini <<'TOOLS'
[binaries]
mesa_clc = '/r/overlay-tools/src/compiler/clc/mesa_clc'
vtn_bindgen2 = '/r/overlay-tools/src/compiler/spirv/vtn_bindgen2'
asahi_clc = '/r/overlay-tools/src/asahi/clc/asahi_clc'
TOOLS
meson setup /r/overlay-runtime "$src" "${options[@]}" --native-file /r/overlay-tools.ini \
  -Dllvm=disabled -Dspirv-tools=disabled -Dmesa-clc=system -Dprecomp-compiler=system > /r/out/runtime-setup.log 2>&1
ninja -C /r/overlay-runtime -j4 > /r/out/runtime-build.log 2>&1
DESTDIR=/r/overlay-stage meson install -C /r/overlay-runtime --no-rebuild > /r/out/stage.log 2>&1
python3 "$src/src/asahi/tools/native-gl-qualification/make-overlay.py" \
  --stage /r/overlay-stage --source "$src" --commit "$commit" --architecture AArch64 --output /r/native-overlay \
  > /r/out/overlay-check.log 2>&1
cp /r/native-overlay/MANIFEST.json /r/out/MANIFEST.json
tar -C /r/native-overlay -cf - MANIFEST.json LICENSE.rst licenses usr | \
  zstd -T2 -q -o "/r/out/mesa-${commit:0:12}-fedora45-aarch64-overlay.tar.zst"
cd /r/out
sha256sum ./*.tar.zst MANIFEST.json > SHA256SUMS
sha256sum -c SHA256SUMS
