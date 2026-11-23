%global commit a0acd9af12346c870ee1538947cbe9f2740cb7fe
# The upstream Makefiles set their own flags (-O3 -Werror) and no -g.
%global debug_package %{nil}
Name: omarchy-ane-tools
Version: 0.5.13
Release: 2%{?dist}
Summary: Apple Neural Engine userspace tools for the in-kernel ANE driver
License: GPL-2.0-only OR MIT
URL: https://github.com/joshuaswarren/omarchy-ane
Source0: omarchy-ane-tools-%{commit}.tar.gz
# The full upstream archive contains unrelated binary research inputs. Keep
# the verified URL/hash in sources.json; distribute only the recipe in SRPMs.
NoSource: 0
Source3: fix-smoke.py
ExclusiveArch: aarch64
BuildRequires: gcc make binutils libdrm-devel python3
Requires: python3
# The device policy (/dev/accel/accel*: group accel, mode 0660, the session
# user's ACL) and the accel group come from the platform, on every install.
Requires: aurora-platform-core >= 44-51

%description
Userspace for the Apple Neural Engine driver that the Aurora kernel ships
(ane and ane_t6021, /dev/accel/accel0): omarchy-ane-run, built from libane,
the omarchy-ane-smoke check with its two add fixtures, and
omarchy-ane-firmware-fetch, which installs an M2-family Mac's own ANE
firmware from Apple's servers when the owner runs it. The package carries no
Apple firmware, no kernel module and no device-tree overlays.

%prep
%autosetup -n omarchy-ane-%{commit}

%build
python3 %{SOURCE3}
make -C libane libane
make -C tools ane-run

%check
# Host-only, no device or network. tools/test_ane_smoke.py is left out: it
# times fake ANE calls against a 2 s limit and fails on slow (emulated) builders.
python3 tools/test_ane_firmware_fetch.py

%install
install -Dm755 tools/ane-run %{buildroot}%{_bindir}/omarchy-ane-run
install -Dm755 packaging/omarchy-ane-smoke %{buildroot}%{_bindir}/omarchy-ane-smoke
install -Dm755 packaging/omarchy-ane-firmware-fetch %{buildroot}%{_bindir}/omarchy-ane-firmware-fetch
# omarchy-ane-smoke looks for its programs here.
for gen in h13 h14; do
  install -Dm644 fixtures/$gen-anec/add/program-0.anec \
    %{buildroot}%{_datadir}/omarchy-ane/fixtures/$gen-anec/add/program-0.anec
done

%files
%license LICENSE
%{_bindir}/omarchy-ane-run
%{_bindir}/omarchy-ane-smoke
%{_bindir}/omarchy-ane-firmware-fetch
%{_datadir}/omarchy-ane/

%changelog
* Mon Nov 23 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.5.13-2
- Drop the udev rule and the accel group: aurora-platform-core 44-51 sets
  the /dev/accel policy on every install, so it no longer depends on
  whether these tools are installed.

* Tue Nov 17 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.5.13-1
- Update to upstream 0.5.13.

* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.5.7-2
- Add accel permissions and relocatable smoke lookup for distro parity.

* Fri Oct 30 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.5.7-1
- Initial package: the userspace half of omarchy-ane 0.5.7 for the kernel's
  own ANE driver.
