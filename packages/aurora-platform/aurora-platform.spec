Name: aurora-platform
Version: 44
Release: 11%{?dist}
Summary: Aurora Apple Silicon hardware stack
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
BuildRequires: systemd-rpm-macros
Requires: aurora-platform-core = %{version}-%{release}
Requires: fastfetch >= 2.68.1-2
Requires: linux-firmware amd-gpu-firmware intel-gpu-firmware nvidia-gpu-firmware
Requires: iwlwifi-dvm-firmware iwlwifi-mvm-firmware realtek-firmware
Requires: aurora-sep libfprint(aurora-sep) = 4
Requires: aurora-firstboot avd-fw upower >= 1.91.4
Requires: kernel-aurora aura uboot-aurora aurora-release aurora-logos aurora-firmware aurora-bless aurora-neo-platform-config tiny-dfr

Source100: README
Source101: aurora-platform-core.conf
Source102: 50-after-swapfile.conf
Source103: 61-aurora-dmi-id.rules
Source104: 60-aurora-dmi-vendor.hwdb

%description
Aurora Apple Silicon hardware stack.

%package core
Summary: Aurora hardware services without a kernel or boot chain
# The Fedora Asahi metapackages require the stock kernel-16k. This package
# keeps the hardware services they bring in and lets the stock kernel go.
Provides: asahi-platform-metapackage = %{version}-%{release}
Provides: asahi-platform-metapackage-core = %{version}-%{release}
Provides: asahi-platform-metapackage-audio = %{version}-%{release}
Obsoletes: asahi-platform-metapackage < 1
Obsoletes: asahi-platform-metapackage-core < 1
Obsoletes: asahi-platform-metapackage-audio < 1
Conflicts: asahi-platform-metapackage < 1
Requires: update-m1n1 asahi-scripts dracut-asahi asahi-fwupdate
Requires: speakersafetyd speakerguardd
Requires: aurora-audio alsa-ucm-conf-aurora
# BlueZ 5.86 attempts an empty default-parameter transaction at startup.
# 5.87 includes the upstream empty-TLV fix; retain real error reporting.
Requires: bluez >= 5.87

%description core
The Apple Silicon hardware services that every Aurora system needs: the
boot.bin assembler (update-m1n1), vendor firmware in the initramfs
(dracut-asahi), firmware refresh (asahi-fwupdate), speaker protection
(speakersafetyd and speakerguardd), and the Aurora audio graphs and UCM
profiles. It installs no kernel, bootloader or release identity, so it fits
a Fedora Asahi Remix install whose kernel and boot chain are managed
separately. It replaces asahi-platform-metapackage, whose -core subpackage
requires the stock kernel-16k, and is protected from removal in the same way.

%prep

%build

%install
install -Dm644 %{SOURCE100} %{buildroot}%{_docdir}/aurora-platform/README
install -Dm644 %{SOURCE101} %{buildroot}%{_sysconfdir}/dnf/protected.d/aurora-platform-core.conf
install -Dm644 %{SOURCE102} %{buildroot}%{_unitdir}/var-swap-swapfile2.swap.d/50-after-swapfile.conf
install -Dm644 %{SOURCE103} %{buildroot}%{_udevrulesdir}/61-aurora-dmi-id.rules
install -Dm644 %{SOURCE104} %{buildroot}%{_udevhwdbdir}/60-aurora-dmi-vendor.hwdb

%files
%{_docdir}/aurora-platform/

%files core
%config(noreplace) %{_sysconfdir}/dnf/protected.d/aurora-platform-core.conf
%{_unitdir}/var-swap-swapfile2.swap.d/
%{_udevrulesdir}/61-aurora-dmi-id.rules
%{_udevhwdbdir}/60-aurora-dmi-vendor.hwdb

%changelog
* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-11
- Update the model examples in the DMI udev rule and hwdb comments to the
  product name without its release date.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-10
- Name the DMI vendor "Apple" (hwdb) instead of "Apple Inc.", so the
  hardware model reads "Apple MacBook Pro (...)".

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-9
- Keep the firmware's product name unchanged in udev's ID_MODEL, so the
  hardware model is not shown with parentheses replaced by underscores.

* Sat Oct 31 2026 Aurora Silicon <ryan@aurorasilicon.org> - 44-8
- Require the BlueZ empty-parameter fix and serialize the second swapfile.

* Fri Oct 30 2026 Aurora Silicon <ryan@aurorasilicon.org> - 44-7
- Split the hardware services into aurora-platform-core. It replaces the
  Fedora Asahi metapackages without pulling the stock kernel, and dnf
  protects it from removal.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
