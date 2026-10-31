%global commit 927013f5480768b07c8e62a866e1514c41aba778
%global debug_package %{nil}
%global __provides_exclude_from ^%{_prefix}/lib/mil-hwx-compiler/.*$
%global __requires_exclude ^(libobjc|libgnustep-base)\.so.*$
Name: mil-hwx-compiler
Version: 0.3.1
Release: 1%{?dist}
Summary: Open MIL to ANE HWX and ANEC compiler
License: MIT AND LGPL-2.1-or-later
URL: https://github.com/joshuaswarren/mil-hwx-compiler
Source0: mil-hwx-compiler-%{commit}.tar.gz
# The full upstream archive contains unrelated binary research inputs. Keep
# the verified URL/hash in sources.json; distribute only the recipe in SRPMs.
NoSource: 0
Source1: libobjc2-a1faad66cee79f29c4ca268b004111edc33a2ae2.tar.gz
Source2: gnustep-make-d0349cc83a23367acdc53df364f73504c281b26c.tar.gz
Source3: gnustep-base-3d7013e144b153abcd6c088dc8d6c64ebd43bc4b.tar.gz
Source4: build-runtime.sh
Source5: install-runtime.sh
ExclusiveArch: aarch64
BuildRequires: clang lld cmake ninja-build make pkgconf-pkg-config
BuildRequires: libffi-devel libxml2-devel libicu-devel openssl-devel zlib-devel robin-map-devel
BuildRequires: gcc-c++ python3 patchelf
# Libraries are private, not ABI-compatible with the system GNUstep runtime.
Provides: bundled(libobjc2)
Provides: bundled(gnustep-base)

%description
MIT-licensed mil-hwxc from upstream v0.3.1, with a private ARC-capable
GNUstep runtime (MIT / LGPL-2.1-or-later). Compiles open MIL input without
Apple frameworks, firmware, models or a device. Does not install a driver.

%prep
%autosetup -n mil-hwx-compiler-%{commit}
tar -xzf %{SOURCE1} -C ..
tar -xzf %{SOURCE2} -C ..
tar -xzf %{SOURCE3} -C ..

%build
JOBS=8 bash %{SOURCE4} ..
make build/mil-hwxc GNUSTEP_PREFIX="$PWD/.gnustep" CXX=clang++

%check
export LD_LIBRARY_PATH="$PWD/.gnustep/lib"
make test-h13 GNUSTEP_PREFIX="$PWD/.gnustep" CXX=clang++
python3 tests/test_h14_fixture_programs.py build/mil-hwxc

%install
bash %{SOURCE5} %{buildroot}%{_prefix} ..

%files
%{_bindir}/mil-hwxc
%{_prefix}/lib/mil-hwx-compiler/
%license %{_datadir}/licenses/mil-hwx-compiler/

%changelog
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.3.1-1
- Package upstream v0.3.1 with pinned private ARC dependencies.
