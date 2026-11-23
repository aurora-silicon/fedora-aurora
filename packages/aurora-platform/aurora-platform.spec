%global selinuxtype targeted
%global modulename aurora_platform

Name: aurora-platform
Version: 44
Release: 53%{?dist}
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
# T6050 boots without arm64.nomte: 7.3.0-37 keeps MTE off on an Apple SoC
# whose device tree reserves no MTE tag storage; aura 1.0.0~b13 reserves it.
Requires: kernel-aurora >= 7.3.0-37
Requires: aura >= 1.0.0~b13
Requires: kernel-aurora aura uboot-aurora aurora-release aurora-logos aurora-firmware aurora-bless aurora-neo-platform-config aurora-m5-platform-config tiny-dfr
# GameMode with Aurora's settings on Plasma and GNOME installs, new and
# upgraded (images also list both). Weak: `dnf remove aurora-gamemode gamemode`
# keeps them off.
Recommends: (aurora-gamemode if (plasma-workspace or gnome-shell))

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
Source115: aurora-wake-for-network
Source116: 63-aurora-wake-for-network.rules
Source117: aurora-grub-uuid
Source118: 90-aurora-reboot-watchdog.conf
Source119: aurora-early-kms-wait.sh
Source120: 64-aurora-trackpad-clicks.rules
Source121: aurora-kdump-dracut.conf
Source122: aurora-kdump.service.conf
Source123: aurora-kdump-setup
Source124: aurora-kdump-clock-module-setup.sh
Source125: aurora-kdump-clock.sh
Source126: 60-aurora-t6041-trackpad.quirks
Source127: aurora-power-defaults.service
Source128: aurora-irq-steerable
Source129: 60_aurora-apple-keys.gschema.override
Source130: 70-aurora-accel.rules
Source131: aurora-accel.sysusers
Source132: 90-aurora-cpufreq.conf

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
# The established protection daemons stay installed as the fallback;
# aurora-speaker-upgrade moves a Mac to v2 only when its self-check passes.
Requires: speakersafetyd speakerguardd
Requires: speakerguardd-v2 >= 1.0.0~alpha.2-0.51 aurora-speaker-upgrade >= 0.1-0.18
Requires: aurora-audio >= 4.1-12
Requires: alsa-ucm-conf-aurora
# BlueZ 5.86 attempts an empty default-parameter transaction at startup.
# 5.87 includes the upstream empty-TLV fix; retain real error reporting.
Requires: bluez >= 5.87
Requires: aurora-camera-denoise
# The Wi-Fi firmware follows the installed macOS, as on macOS.
Requires: aurora-wifi-firmware
# The VA-API driver for the video decoder, so players and browsers that
# use VA-API decode in hardware (images install it; this brings it to Macs
# that update with dnf).
Requires: libva-v4l2-request-avd
Requires: aurora-kbd-light
# One built-in panel brightness, shared with the boot loader and macOS
# through NVRAM backlight-nits.
Requires: aurora-panel-nits
# NVRAM tools that parse the current NVRAM v3 stores, and the Bluetooth
# pairings made in macOS (they replace asahi-nvram and asahi-btsync).
Requires: aurora-nvram aurora-btsync
# The Aurora repository with its key and dnf vendor policies, so a Fedora
# Asahi Remix system with these services keeps following Aurora's builds.
Requires: aurora-repos
Requires: tuned
Requires: aurora-power-budget
# Wake for network access (magic packet) follows the power adapter.
Requires: ethtool iw
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

%package kdump
Summary: Save Linux crashes to /var/crash with kdump
Requires: aurora-platform-core = %{version}-%{release}
Requires: kdump-utils makedumpfile grubby

%description kdump
Opt-in crash dumps for Linux on Apple silicon. iBoot keeps no record of a
Linux panic, so a crash kernel saves the vmcore and the crashed kernel's log
to /var/crash; aurora-panic-log lists them. Installing this package enables
kdump.service and reserves 512 MiB for the crash kernel from the next
boot; removing it undoes both. See docs/kdump.md for the Macs it is
tested on.

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
install -Dm755 %{SOURCE128} %{buildroot}%{_libexecdir}/aurora/aurora-irq-steerable
install -Dm644 %{SOURCE103} %{buildroot}%{_udevrulesdir}/61-aurora-dmi-id.rules
install -Dm644 %{SOURCE111} %{buildroot}%{_udevrulesdir}/62-aurora-gpu-render-only.rules
install -Dm644 %{SOURCE104} %{buildroot}%{_udevhwdbdir}/60-aurora-dmi-vendor.hwdb
install -Dm755 %{SOURCE105} %{buildroot}%{_prefix}/lib/dracut/modules.d/91aurora-usb4/module-setup.sh
install -Dm755 %{SOURCE106} %{buildroot}%{_prefix}/lib/dracut/modules.d/91aurora-early-kms/module-setup.sh
install -Dm755 %{SOURCE107} %{buildroot}%{_prefix}/lib/dracut/modules.d/91aurora-early-kms/aurora-early-kms.sh
install -Dm755 %{SOURCE119} %{buildroot}%{_prefix}/lib/dracut/modules.d/91aurora-early-kms/aurora-early-kms-wait.sh
install -Dpm0644 %{SOURCE114} %{buildroot}%{_prefix}/lib/dracut/dracut.conf.d/90-aurora-ane.conf
install -Dpm0644 %{SOURCE132} %{buildroot}%{_prefix}/lib/dracut/dracut.conf.d/90-aurora-cpufreq.conf
install -Dm755 %{SOURCE108} %{buildroot}%{_libexecdir}/aurora/aurora-grub-console
install -Dm755 %{SOURCE117} %{buildroot}%{_libexecdir}/aurora/aurora-grub-uuid
install -Dm644 %{SOURCE112} %{buildroot}%{_prefix}/lib/tuned/profiles/aurora-performance/tuned.conf
install -Dm755 %{SOURCE113} %{buildroot}%{_libexecdir}/aurora/aurora-ppd-config
install -Dm755 %{SOURCE115} %{buildroot}%{_libexecdir}/aurora/aurora-wake-for-network
install -Dm644 %{SOURCE116} %{buildroot}%{_udevrulesdir}/63-aurora-wake-for-network.rules
install -Dm644 %{SOURCE120} %{buildroot}%{_udevrulesdir}/64-aurora-trackpad-clicks.rules
# /dev/accel (the Neural Engine) for the accel group and the local session
# user, instead of systemd's mode 0666; rpm creates the group from sysusers.d.
install -Dm644 %{SOURCE130} %{buildroot}%{_udevrulesdir}/70-aurora-accel.rules
install -Dm644 %{SOURCE131} %{buildroot}%{_sysusersdir}/aurora-accel.conf
install -Dm644 %{SOURCE126} %{buildroot}%{_datadir}/libinput/60-aurora-t6041-trackpad.quirks
install -Dm644 %{SOURCE129} %{buildroot}%{_datadir}/glib-2.0/schemas/60_aurora-apple-keys.gschema.override
install -Dm644 %{SOURCE127} %{buildroot}%{_unitdir}/aurora-power-defaults.service
# Wanted by sysinit.target itself: a preset would not reach Macs that
# already have aurora-platform-core. ConditionFirmware skips machines that
# are not Apple silicon Macs.
install -d %{buildroot}%{_unitdir}/sysinit.target.wants
ln -s ../aurora-power-defaults.service %{buildroot}%{_unitdir}/sysinit.target.wants/aurora-power-defaults.service
install -Dm644 %{SOURCE118} %{buildroot}%{_prefix}/lib/systemd/system.conf.d/90-aurora-reboot-watchdog.conf
install -Dm644 %{SOURCE121} %{buildroot}%{_prefix}/lib/kdump/dracut.conf.d/99-zz-aurora.conf
install -Dm644 %{SOURCE122} %{buildroot}%{_unitdir}/kdump.service.d/50-aurora-kdump.conf
install -Dm755 %{SOURCE123} %{buildroot}%{_libexecdir}/aurora/aurora-kdump-setup
install -Dm755 %{SOURCE124} %{buildroot}%{_prefix}/lib/dracut/modules.d/99aurora-kdump-clock/module-setup.sh
install -Dm755 %{SOURCE125} %{buildroot}%{_prefix}/lib/dracut/modules.d/99aurora-kdump-clock/aurora-kdump-clock.sh

%posttrans core
# Give an existing /dev/accel node the rule's group and mode now, not at the
# next boot. systemd-udev's file trigger only marks udevd for a reload, so
# reload first; and send an add event, since a change event does not
# reapply GROUP and MODE. Skipped in a chroot (image or mock build) and
# without a running udevd, so a build never touches the build host's nodes.
if [ -S /run/udev/control ] && ! systemd-detect-virt -q --chroot; then
  udevadm control --reload >/dev/null 2>&1 || :
  udevadm trigger --action=add --subsystem-match=accel >/dev/null 2>&1 || :
fi
# Fedora's flicker-free GRUB output, once per system; see the script.
%{_libexecdir}/aurora/aurora-grub-console || :
# A grub.cfg whose only stale lines are partition UUID searches; see the script.
%{_libexecdir}/aurora/aurora-grub-uuid || :
%{_libexecdir}/aurora/aurora-ppd-config || :
# MTE stays off on the M5 (T8142) until it is qualified there. The M5 Pro
# and Max (T6050) run with MTE: aura reserves the tag storage, and without
# that reservation the kernel keeps MTE off by itself.
if tr '\0' '\n' < /proc/device-tree/compatible 2>/dev/null | grep -qx 'apple,t8142' &&
    ! grep -qE '(^|[[:space:]])arm64\.nomte([[:space:]]|$)' /etc/kernel/cmdline 2>/dev/null; then
  grubby --update-kernel=ALL --args=arm64.nomte || :
fi

# 44-37 to 44-44 also added arm64.nomte on T6050 Macs, with grubby, which
# writes it to every boot entry, /etc/default/grub and /etc/kernel/cmdline.
# Take it back out once, on the update from one of those releases.
%triggerpostun core -- aurora-platform-core < 44-45
if tr '\0' '\n' < /proc/device-tree/compatible 2>/dev/null | grep -qx 'apple,t6050' &&
    grep -qsE '(^|[[:space:]"])arm64\.nomte([[:space:]"]|$)' /etc/kernel/cmdline /etc/default/grub /boot/loader/entries/*.conf; then
  grubby --update-kernel=ALL --remove-args=arm64.nomte || :
fi

# Also cover tuned-ppd installed/upgraded without an aurora-platform update.
# The file remains owned by tuned-ppd as %%config(noreplace).
# Transaction file triggers look up installed packages by directory prefix.
%transfiletriggerin core -- %{_sysconfdir}/tuned/
%{_libexecdir}/aurora/aurora-ppd-config || :

%post kdump
# Installing the package is the opt-in; see the script.
if [ "$1" -eq 1 ]; then
  %{_libexecdir}/aurora/aurora-kdump-setup enable || :
fi

%preun kdump
if [ "$1" -eq 0 ]; then
  %{_libexecdir}/aurora/aurora-kdump-setup disable || :
fi

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
%{_libexecdir}/aurora/aurora-irq-steerable
%{_unitdir}/aurora-power-defaults.service
%{_unitdir}/sysinit.target.wants/aurora-power-defaults.service
%{_udevrulesdir}/61-aurora-dmi-id.rules
%{_udevrulesdir}/62-aurora-gpu-render-only.rules
%{_udevrulesdir}/63-aurora-wake-for-network.rules
%{_udevrulesdir}/64-aurora-trackpad-clicks.rules
%{_udevrulesdir}/70-aurora-accel.rules
%{_sysusersdir}/aurora-accel.conf
%{_datadir}/libinput/60-aurora-t6041-trackpad.quirks
%{_datadir}/glib-2.0/schemas/60_aurora-apple-keys.gschema.override
%{_udevhwdbdir}/60-aurora-dmi-vendor.hwdb
%{_prefix}/lib/systemd/system.conf.d/90-aurora-reboot-watchdog.conf
%{_prefix}/lib/dracut/modules.d/91aurora-usb4/
%{_prefix}/lib/dracut/modules.d/91aurora-early-kms/
%{_prefix}/lib/dracut/dracut.conf.d/90-aurora-ane.conf
%{_prefix}/lib/dracut/dracut.conf.d/90-aurora-cpufreq.conf
%{_libexecdir}/aurora/aurora-grub-console
%{_libexecdir}/aurora/aurora-grub-uuid
%{_libexecdir}/aurora/aurora-ppd-config
%{_libexecdir}/aurora/aurora-wake-for-network
%dir %{_prefix}/lib/tuned/profiles/aurora-performance
%{_prefix}/lib/tuned/profiles/aurora-performance/tuned.conf

%files kdump
%{_libexecdir}/aurora/aurora-kdump-setup
%{_prefix}/lib/kdump/dracut.conf.d/99-zz-aurora.conf
%{_prefix}/lib/dracut/modules.d/99aurora-kdump-clock/
%dir %{_unitdir}/kdump.service.d
%{_unitdir}/kdump.service.d/50-aurora-kdump.conf

%files selinux
%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2
%ghost %verify(not md5 size mode mtime) %{_sharedstatedir}/selinux/%{selinuxtype}/active/modules/200/%{modulename}

%changelog
* Mon Nov 23 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-53
- The initramfs carries the CPU frequency driver (apple-soc-cpufreq), so the
  cores leave the boot loader's clock in the initramfs instead of after the
  switch to the real root. MacBook Neo: frequency scaling from 3.4-3.7 s
  instead of 7.0-7.6 s, gdm 1.2 s earlier (9.12 s instead of 10.40 s, median
  of 3 boots each).

* Mon Nov 23 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-51
- /dev/accel/accel* (the Neural Engine) is mode 0660, group accel, with a
  uaccess ACL for the user of the active local session
  (70-aurora-accel.rules, group from aurora-accel.conf). systemd's default
  rule left it mode 0666; the only narrower rule was in the opt-in
  omarchy-ane-tools, which no longer carries one. %posttrans reloads udev
  and sends existing accel nodes an add event (not in a chroot). Users
  outside the local session, such as ssh-only accounts, now need the accel
  group ("usermod -aG accel USER").

* Mon Nov 23 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-50
- aurora-kdump-setup (aurora-platform-kdump) reports a failed
  systemctl enable/disable of kdump.service and a failed grubby
  --remove-args=crashkernel, with the command to run instead. It used to
  discard both. The rest of the step still runs and it still exits 0, so
  the %%post/%%preun outcome is unchanged.

* Sat Nov 21 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-48
- The Mission Control key (F3, keysym XF86LaunchA) opens and closes the
  GNOME Activities overview, as Mission Control does on macOS
  (60_aurora-apple-keys.gschema.override). GNOME bound nothing to it.

* Sat Nov 21 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-47
- Power defaults on every Apple silicon Mac (aurora-power-defaults.service,
  ConditionFirmware=device-tree-compatible(apple,arm-platform)), replacing
  the M4 Max-only aurora-t6041-power.service: PCIe ASPM policy
  powersupersave and kernel.sched_util_clamp_min_rt_default=0. The ASPM
  write may fail (pcie_aspm=off) without skipping the sysctl. Ordered before
  aurora-power-modes, so its boot baseline is these values. Same unit as
  ALARM (alarm-aurora#332 by AxxzyWasTaken). Idle power -14 to -31 % on the
  T8140, T6040, T6000 and T8112 with no xruns or Wi-Fi/Bluetooth drops.

* Fri Nov 20 2026 Diljit Singh <hey@djdev.me> - 44-46
- Require aurora-m5-platform-config, the MacBook Pro (M5 Pro, J714s) deep
  sleep configuration, as aurora-neo-platform-config is required for the
  Neo. It does nothing on any other Mac.

* Fri Nov 20 2026 Diljit Singh <hey@djdev.me> - 44-45
- MTE on the M5 Pro and Max (T6050): add arm64.nomte only on the M5
  (T8142), and take back out, once on the update from 44-44 or older, the
  arm64.nomte that 44-37 to 44-44 added on T6050 Macs. aura 1.0.0~b13
  reserves the T6050 tag storage, and kernel-aurora 7.3.0-37 and later
  keep MTE off by themselves on an Apple SoC whose device tree reserves
  none (aurora-silicon/linux#1639); aurora-platform requires both.
  Measured on the MacBook Pro (M5 Pro, J714s): the M5 default has run
  with MTE on since 11-12 (tagged stress, mtesuite and the deep-sleep
  gates); T8142 has had no MTE trial yet.

* Fri Nov 20 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-44
- Recommend aurora-gamemode (and with it gamemode) on Plasma and GNOME
  installs, so existing desktops get GameMode with Aurora's settings on
  upgrade. Measured on J616s and Neo: -9 to -11 % frame time at two frames
  in flight at the same energy per frame where GameMode pins (four or more
  P cores), unchanged where it does not.

* Fri Nov 20 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-43
- aurora-platform-core requires speakerguardd-v2 and aurora-speaker-upgrade,
  whose preset moves each Mac to v2 at boot when its self-check passes.
  speakersafetyd and speakerguardd 0.1 stay installed and keep any Mac the
  self-check refuses.

* Thu Nov 19 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-42
- irqbalance runs on an Apple silicon Mac when its device tree's interrupt
  controller is the first AIC (compatible apple,aic), which can steer
  interrupts, instead of when the SoC is the T8103: an ExecCondition
  (aurora-irq-steerable) replaces the SoC check. Same result on every Mac
  supported today.

* Sun Nov 15 2026 AxxzyWasTaken <axxzytte@gmail.com> - 44-41
- M4 Max (T6041) power defaults (aurora-t6041-power.service): PCIe ASPM
  policy powersupersave, so the Wi-Fi/Bluetooth and SD reader links use the
  L1.1 and L1.2 substates both ends support, and no utilization floor for
  realtime threads (kernel.sched_util_clamp_min_rt_default=0), so threaded
  IRQs and PipeWire no longer run their CPU at its top clock. The unit is
  skipped on every other Mac. Measured on a J616c running Arch; not tested
  on a J614c or on Fedora.

* Sun Nov 15 2026 AxxzyWasTaken <axxzytte@gmail.com> - 44-40
- Turn libinput's size-based palm detection off for the M4 Max MacBook Pro
  trackpads (J614c, J616c; 60-aurora-t6041-trackpad.quirks). The kernel
  reports their palms as MT_TOOL_PALM (linux#636), and a resting palm's
  touch size (about 1060) is under the Apple MTP threshold of 1600, so the
  threshold never caught it. Same as the J700 quirk. Tested on a J616c
  running Arch; not on a J614c or on Fedora.

* Fri Nov 13 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-39
- aurora-platform-core requires aurora-wifi-firmware: the ESP's Wi-Fi
  firmware follows the installed macOS's, read from the macOS system volume
  at boot and used from the next boot.

* Thu Nov 12 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-38
- New opt-in subpackage aurora-platform-kdump: save Linux's own crashes
  with kdump. iBoot keeps no record of a Linux panic, so a crash kernel
  writes the vmcore and the crashed kernel's log to /var/crash, and
  aurora-panic-log lists them. Installing it enables kdump.service and adds
  crashkernel=512M unless one is set; removing it disables the service and
  removes the crashkernel= it added. kdump-utils' 320 MiB default is too
  small once the initramfs is unpacked whole (next item): the M1 Pro's
  crash kernel ran out of memory and saved nothing.
- The crash kernel's initramfs gets nvme_apple (kdump-utils replaces
  dracut-asahi's module list) and leaves out the drivers of coprocessors
  and buses the crashed kernel left running; probing them stalled the
  crash kernel before the disk came up.
- A dracut hook in that initramfs sets the clock from the panic time in
  the crashed kernel's vmcoreinfo (the crash kernel has no SMC RTC), so
  dump directories carry the panic time.
- kdump.service is skipped, not failed, on a boot without crash kernel
  memory.
- Build that initramfs without the squashfs layer. Behind it sits a small
  busybox /init, and with Fedora 44's dracut 108 that /init never loaded
  its first module in the crash kernel, so the MacBook Air (M2) saved no
  dump and its watchdog restarted it after about 3 minutes.
- Tested with sysrq-c on 7.3.0-aurora-fleet67 with this initramfs:
  MacBook Air (M2) at 320 MiB, 222 MiB vmcore, back on the default kernel
  17 s after the panic; MacBook Pro (M1 Pro) at 512 MiB, 269 MiB vmcore,
  back after 42 s.

* Wed Nov 11 2026 DjDeveloperr <hey@djdev.me> - 44-37
- Boot M5 (T8142) and M5 Pro/Max (T6050) Macs with arm64.nomte:
  aurora-platform-core adds it with grubby to every boot entry and to
  future kernels when the device tree names one of those chips. The MTE
  tag store is unreserved until the aura change lands.

* Wed Nov 11 2026 DjDeveloperr <hey@djdev.me> - 44-36
- Play trackpad clicks from the host, as macOS does, on Macs whose MTP
  trackpad has a haptic actuator: 64-aurora-trackpad-clicks.rules sets
  hid_magicmouse haptic_press when the trackpad binds. macOS takes click
  control from the actuator at boot. Tested on a MacBook Pro (M5 Pro),
  where the owner reported "haptic works"; the force-click threshold is not
  touch-tested yet. An empty /etc/udev/rules.d file of the same name keeps
  the firmware's click.

* Wed Nov 11 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-35
- 91aurora-early-kms waits up to 2 s before the pivot for appledrm's DRM
  device, so Plymouth takes it over while the initramfs udevd runs instead
  of after an fbdev modeset blanks the panel

* Wed Nov 11 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-34
- Require aurora-nvram and aurora-btsync, which replace asahi-nvram and
  asahi-btsync: stock asahi-nvram panics on current NVRAM v3 stores, and
  aurora-btsync refreshes the keys of devices macOS paired again.

* Wed Nov 11 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-33
- Require aurora-panel-nits: the built-in panel starts at the boot loader's
  NVRAM backlight-nits level instead of systemd-backlight's saved level, and
  the user's level is stored back to NVRAM, so the panel does not step when
  Linux takes over and the boot loader and macOS start at the same level.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-32
- Reset a stuck reboot after 2 minutes: set RebootWatchdogSec and
  KExecWatchdogSec to 2min. The Apple SoC watchdog cannot time out later than
  about 178 s, so with systemd's default of 10 min the kernel kept feeding it
  and a reboot that stalled was not reset for over 10 minutes. Tested on a
  MacBook Air (M2): a reboot wedged before the final reboot call is reset
  2 min after the watchdog is armed, 1 min with 1min.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-31
- SELinux: stop logging three denials on every login. pam_gdm scans
  /proc/keys for the disk passphrase, and listing needs "view" on each key;
  the session worker (xdm_t) may not view cfg80211's regulatory certificate
  keys when a platform service loaded cfg80211 (unconfined_service_t). It
  never needs them: dontaudit only, no new access.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-30
- Bring the external displays' Type-C chain (I2C controller, retimer or PD
  controller, Type-C PHY) up in the initramfs with the display: appledrm
  waits for every DCP, so the internal panel showed black from its DCP's
  start until the real root loaded the I2C controller.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-29
- Require aurora-power-budget: Power Saver gets a CPU power budget, as
  macOS Low Power Mode does.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-28
- Regenerate a grub.cfg whose only stale lines are partition UUID searches
  (aurora-grub-uuid): a 'search --fs-uuid --set=boot' for an ESP UUID that no
  longer exists made GRUB print an error on screen on every boot.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 44-27
- Wake for network access as macOS defaults it on laptops: magic-packet
  wake is armed on wired interfaces that support it and on Wi-Fi phys that
  offer magic-packet WoWLAN while the power adapter is connected, and
  disarmed on battery. /etc/aurora/wake-for-network can set always or
  never instead.

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
