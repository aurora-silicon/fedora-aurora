%global selinuxtype targeted
%global modulename aurora_platform

Name: aurora-platform
Version: 44
Release: 26%{?dist}
Summary: Aurora Apple Silicon hardware stack
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
BuildRequires: systemd-rpm-macros
BuildRequires: selinux-policy-devel make bzip2
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
Source105: usb4-module-setup.sh
Source106: early-kms-module-setup.sh
Source107: aurora-early-kms.sh
Source108: aurora-grub-console
Source109: aurora_platform.te
Source110: 50-aurora-irqbalance.conf
Source111: 62-aurora-gpu-render-only.rules
Source112: aurora-performance.conf
Source113: aurora-ppd-config
Source114: 90-aurora-ane.conf

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
# Use the established protection daemons; v2 is not shipped in images.
Requires: speakersafetyd speakerguardd
Requires: aurora-audio >= 4.1-12
Requires: alsa-ucm-conf-aurora
# BlueZ 5.86 attempts an empty default-parameter transaction at startup.
# 5.87 includes the upstream empty-TLV fix; retain real error reporting.
Requires: bluez >= 5.87
Requires: aurora-camera-denoise
# The VA-API driver for the video decoder, so players and browsers that
# use VA-API decode in hardware (images install it; this brings it to Macs
# that update with dnf).
Requires: libva-v4l2-request-avd
Requires: aurora-kbd-light
# The Aurora repository with its key and dnf vendor policies, so a Fedora
# Asahi Remix system with these services keeps following Aurora's builds.
Requires: aurora-repos
Requires: tuned
Requires: python3
Requires: (aurora-platform-selinux = %{version}-%{release} if selinux-policy-%{selinuxtype})

%description core
The Apple Silicon hardware services that every Aurora system needs: the
boot.bin assembler (update-m1n1), vendor firmware in the initramfs
(dracut-asahi), firmware refresh (asahi-fwupdate), speaker protection
(speakersafetyd and speakerguardd), the Aurora audio graphs and UCM
profiles, the noise filter for the built-in camera
(aurora-camera-denoise), and the keyboard backlight that follows the ambient
light sensor (aurora-kbd-light). It installs no kernel, bootloader or release
identity, so it fits a Fedora Asahi Remix install whose kernel and boot
chain are managed separately. It replaces asahi-platform-metapackage, whose
-core subpackage requires the stock kernel-16k, and is protected from removal
in the same way.

%package selinux
Summary: SELinux policy fixes for the Aurora hardware services
Requires: selinux-policy-%{selinuxtype}
Requires(post): selinux-policy-%{selinuxtype}
Requires(post): policycoreutils
Requires(postun): policycoreutils
%{?selinux_requires}

%description selinux
Lets systemd inspect the kernel uevent socket it creates for udev in the
initramfs and keeps across the switch to the real root. The socket is made
before the policy is loaded, so it carries the kernel's label, and every
boot logged a denial for it.

%prep
%setup -q -c -T
cp -p %{SOURCE109} .

%build
%make_build -f %{_datadir}/selinux/devel/Makefile %{modulename}.pp
bzip2 -9 %{modulename}.pp

%install
install -Dpm0644 %{modulename}.pp.bz2 \
    %{buildroot}%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2
install -Dm644 %{SOURCE100} %{buildroot}%{_docdir}/aurora-platform/README
install -Dm644 %{SOURCE101} %{buildroot}%{_sysconfdir}/dnf/protected.d/aurora-platform-core.conf
install -Dm644 %{SOURCE102} %{buildroot}%{_unitdir}/var-swap-swapfile2.swap.d/50-after-swapfile.conf
install -Dm644 %{SOURCE110} %{buildroot}%{_unitdir}/irqbalance.service.d/50-aurora-irqbalance.conf
install -Dm644 %{SOURCE103} %{buildroot}%{_udevrulesdir}/61-aurora-dmi-id.rules
install -Dm644 %{SOURCE111} %{buildroot}%{_udevrulesdir}/62-aurora-gpu-render-only.rules
install -Dm644 %{SOURCE104} %{buildroot}%{_udevhwdbdir}/60-aurora-dmi-vendor.hwdb
install -Dm755 %{SOURCE105} %{buildroot}%{_prefix}/lib/dracut/modules.d/91aurora-usb4/module-setup.sh
install -Dm755 %{SOURCE106} %{buildroot}%{_prefix}/lib/dracut/modules.d/91aurora-early-kms/module-setup.sh
install -Dm755 %{SOURCE107} %{buildroot}%{_prefix}/lib/dracut/modules.d/91aurora-early-kms/aurora-early-kms.sh
install -Dpm0644 %{SOURCE114} %{buildroot}%{_prefix}/lib/dracut/dracut.conf.d/90-aurora-ane.conf
install -Dm755 %{SOURCE108} %{buildroot}%{_libexecdir}/aurora/aurora-grub-console
install -Dm644 %{SOURCE112} %{buildroot}%{_prefix}/lib/tuned/profiles/aurora-performance/tuned.conf
install -Dm755 %{SOURCE113} %{buildroot}%{_libexecdir}/aurora/aurora-ppd-config

%posttrans core
# Fedora's flicker-free GRUB output, once per system; see the script.
%{_libexecdir}/aurora/aurora-grub-console || :
%{_libexecdir}/aurora/aurora-ppd-config || :

# Also cover tuned-ppd installed/upgraded without an aurora-platform update.
# The file remains owned by tuned-ppd as %%config(noreplace).
# Transaction file triggers look up installed packages by directory prefix.
%transfiletriggerin core -- %{_sysconfdir}/tuned/
%{_libexecdir}/aurora/aurora-ppd-config || :

%pre selinux
%selinux_relabel_pre -s %{selinuxtype}

%post selinux
%selinux_modules_install -s %{selinuxtype} %{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2

%postun selinux
%selinux_modules_uninstall -s %{selinuxtype} %{modulename}

%posttrans selinux
%selinux_relabel_post -s %{selinuxtype}

%files
%{_docdir}/aurora-platform/

%files core
%config(noreplace) %{_sysconfdir}/dnf/protected.d/aurora-platform-core.conf
%{_unitdir}/var-swap-swapfile2.swap.d/
%dir %{_unitdir}/irqbalance.service.d
%{_unitdir}/irqbalance.service.d/50-aurora-irqbalance.conf
%{_udevrulesdir}/61-aurora-dmi-id.rules
%{_udevrulesdir}/62-aurora-gpu-render-only.rules
%{_udevhwdbdir}/60-aurora-dmi-vendor.hwdb
%{_prefix}/lib/dracut/modules.d/91aurora-usb4/
%{_prefix}/lib/dracut/modules.d/91aurora-early-kms/
%{_prefix}/lib/dracut/dracut.conf.d/90-aurora-ane.conf
%{_libexecdir}/aurora/aurora-grub-console
%{_libexecdir}/aurora/aurora-ppd-config
%dir %{_prefix}/lib/tuned/profiles/aurora-performance
%{_prefix}/lib/tuned/profiles/aurora-performance/tuned.conf

%files selinux
%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2
%ghost %verify(not md5 size mode mtime) %{_sharedstatedir}/selinux/%{selinuxtype}/active/modules/200/%{modulename}

%changelog
* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-26
- Leave the Neural Engine driver (ane_t6021) out of the initramfs
  (90-aurora-ane.conf). Its probe boots the ANE firmware, about 1.2 s on
  the M2, and the initramfs could not switch to the real root until it
  returned. It now loads from the real root.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-25
- 91aurora-early-kms queues the display devices ahead of the coldplug but no
  longer waits for them. appledrm registers only once every display
  processor, the external ones included, has started, which took about
  1.3 s on the M1 Pro; the root file system and the rest of the initramfs
  waited for it. Plymouth adds the KMS device when it appears.

* Mon Nov 09 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-24
- aurora-platform-core requires libva-v4l2-request-avd, the VA-API driver
  for the video decoder. New images install it, but Macs that update with
  dnf never got it, so VA-API players and browsers had no driver and
  decoded in software.

* Sun Nov 08 2026 Aurora Silicon <hey@djdev.me> - 44-23
- Restore legacy speaker protection as the shipped stack and require the
  restored Asahi DSP profiles. Do not install the speakerguardd v2 preview.


* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-22
- Let plymouthd map a DRM card that the kernel created after the policy
  load and udev has not relabelled yet. Such a node briefly carries the
  targeted policy's xserver_misc_device_t, and plymouthd, still kernel_t
  from the initramfs, logged a map denial on about one boot in ten on the
  Neo.

* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-21
- Require speakerguardd-v2 beside speakersafetyd and speakerguardd 0.1. Its
  fleet gate starts exactly one stack per boot; on a kernel without the v2
  interface (every fleet kernel today) that is the older daemons, as before.

* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-20
- Map tuned-ppd's stock performance profile to aurora-performance, using
  schedutil without inherited boost writes. Preserve custom mappings and
  recheck the stock line when tuned-ppd is installed or upgraded.

* Fri Nov 06 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-19
- Tag the GPU's render-only card mutter-device-ignore. It has no display
  engine, so GNOME Shell failed to open it as a display on every login and
  logged "Failed to open gpu" and a g_close EBADF. Mesa still renders on it
  through the display card.

* Fri Nov 06 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-18
- Add aurora-platform-selinux, pulled in by aurora-platform-core on SELinux
  systems. It lets systemd inspect the kernel uevent socket it creates for
  udev in the initramfs and keeps over the switch to the real root, which
  logged an init_t getattr denial on every boot.
- Start irqbalance only where interrupts can be steered: on other hardware
  and on the M1. From the M1 Pro and M2 on the interrupt controller cannot
  steer them, and irqbalance logged a failure for every PCIe MSI.

* Thu Nov 05 2026 DjDeveloperr <hey@djdev.me> - 44-17
- Require aurora-kbd-light, so the keyboard backlight follows the ambient
  light sensor as on macOS.

* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-16
- Switch GRUB_TERMINAL_OUTPUT from gfxterm to the console once per system
  (aurora-grub-console), so GRUB no longer clears the boot logo. A
  hand-maintained grub.cfg is left alone, and an owner who chooses gfxterm
  again keeps it.

* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-15
- Coldplug the display first in the initramfs (91aurora-early-kms): trigger
  the Apple display subsystem, its DCPs, their device-link suppliers and the
  DRM cards before the rest of the coldplug. On Fedora 45 the initramfs
  pivoted before udev reached them, so appledrm never loaded there and
  Plymouth waited for the real root.

* Mon Nov 02 2026 DjDeveloperr <hey@djdev.me> - 44-14
- Carry the USB4/Thunderbolt router (thunderbolt_apple) in the initramfs
  next to the Type-C port controllers that dracut-asahi carries. Without
  it the ports probe without their router, and a Thunderbolt dock came up
  as USB 2.0 hubs after a LUKS prompt that waited more than ten seconds.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-13
- Require aurora-repos from aurora-platform-core: a Fedora Asahi Remix
  system with Aurora's hardware services gets the Aurora repository and the
  dnf vendor policies that let Aurora's and Fedora's packages replace each
  other on upgrade.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-12
- Pull in aurora-camera-denoise, the noise filter for the built-in camera,
  from aurora-platform-core.

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
