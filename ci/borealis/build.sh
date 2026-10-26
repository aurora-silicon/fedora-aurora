#!/bin/bash
# SPDX-License-Identifier: MIT
set -euo pipefail
ulimit -c 0
kind=${1:?}; commit=${2:?}; release=${3:?}
export TMPDIR=/r/tmp
cat /etc/fedora-release > /r/out/fedora-release.txt
dnf -y -q install rpm-build dnf5-plugins file
D=(--define '_topdir /r/buildroot' --define '_sourcedir /r/SOURCES' --define '_smp_mflags -j4')
if [ "$kind" = native ]; then
  test "$(uname -m)" = aarch64
  spec=/r/SPECS/mesa.spec
else
  test "$kind" = fex
  test "$(uname -m)" = x86_64
  spec=/r/SPECS/mesa-aurora-fex-guest.spec
  D+=(--define "commit $commit" --define 'host_version 26.3.0~devel'
      --define "host_release $release.aurora.borealis.${commit:0:12}%{?dist}")
fi
dnf -y -q builddep --setopt=install_weak_deps=False "${D[@]}" "$spec"
rpm -qa | sort > /r/out/buildroot-rpm-qa.txt
set +e
rpmbuild -br "${D[@]}" "$spec" > /r/out/buildrequires.log 2>&1
br=$?
set -e
test "$br" = 0 || test "$br" = 11
if compgen -G '/r/buildroot/SRPMS/*.buildreqs.nosrc.rpm' >/dev/null; then
  dnf -y -q builddep /r/buildroot/SRPMS/*.buildreqs.nosrc.rpm
fi
set +e
rpmbuild -ba "${D[@]}" "$spec" > /r/out/build.log 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > /r/out/build.rc
test "$rc" = 0
cp /r/buildroot/RPMS/*/*.rpm /r/buildroot/SRPMS/*.rpm /r/out/
cd /r/out
sha256sum ./*.rpm > SHA256SUMS
sha256sum -c --quiet SHA256SUMS
rpm -qp --qf '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}\n' ./*.rpm > packages.txt
