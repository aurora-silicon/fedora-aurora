%global commit 20c328448a51f680ef545b3fb5d1d3a9c6abc9a3
%global selinuxtype targeted
Name: aurora-firstboot
Version: 0.1.13
Release: 8%{?dist}
Summary: Aurora per-install root encryption and Linux account setup
License: MIT
URL: https://github.com/aurora-silicon/aurora-platform
Source0: aurora-firstboot-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: make systemd-rpm-macros
Requires: bash cryptsetup >= 2.8 btrfs-progs util-linux coreutils systemd python3 shadow-utils sudo kbd procps-ng
Requires: dracut policycoreutils selinux-policy-targeted
%{?selinux_requires_min}
Requires(posttrans): policycoreutils libselinux-utils
# The Plasma Setup drop-in moved here from aurora-remix-scripts.
Conflicts: aurora-remix-scripts < 44-5

%description
Shared first-boot account setup and per-install Btrfs encryption. The image
producer supplies immutable filesystem identities and explicit fresh-image
markers; installing this package alone does not arm encryption or setup.

%package -n aurora-power-budget
Summary: CPU power budget for the power-saver profile on Apple silicon
Requires: python3 systemd
Requires: (tuned-ppd or power-profiles-daemon)

%description -n aurora-power-budget
Gives the Power Saver profile a real CPU power limit, like macOS Low Power
Mode: every 100 ms a budget from the device tree energy model is spent on
the frequency steps that buy the most CPU capacity per milliwatt, and each
cluster is capped to its share.
aurora-power-modes drives the rest of each profile: in Power Saver the
realtime threads lose their top-clock floor and the PCIe links use L1.1/L1.2;
every kernel platform-profile handler follows the profile (tuned-ppd does
not drive them on device tree boots); and macOS's "Low Power Mode on
battery" setting is available in /etc/aurora/power-modes.conf (off by
default, as on macOS).
Where the kernel budgets Power Saver itself (apple-clpc), aurora-power-budget
hands it each profile instead and caps the CPU here only while the kernel
does not hold Power Saver; aurora-power-modes leaves that handler alone, so
each handler has one writer.

%package -n aurora-gamemode
Summary: GameMode defaults for Apple silicon: games on the P cores, schedutil kept
Requires: gamemode
Supplements: (gamemode and aurora-platform-core)

%description -n aurora-gamemode
Installs /etc/gamemode.ini so that games started with GameMode
(gamemoderun, or the GameMode switch in Steam, Lutris or Heroic) run on
the performance cores instead of being placed on the efficiency cores,
while the CPU governor stays schedutil rather than GameMode's default
performance governor. Macs with fewer than four performance cores are
left unpinned.

%package -n aurora-secboot
Summary: Signed unified kernel images for the Aurora secure boot path
Requires: python3 systemd systemd-ukify systemd-boot-unsigned sbsigntools openssl
Requires: selinux-policy-targeted
Requires(post): policycoreutils
Requires(postun): policycoreutils
Requires(posttrans): policycoreutils

%description -n aurora-secboot
aurora-secboot builds a unified kernel image (kernel, initramfs and command
line in one PE file) for every kernel that kernel-install adds, signs it with
the owner's UEFI db key when one exists, and can make it the boot loader of
the secure boot path. The command line in the image always carries
lockdown=integrity. Shim and GRUB stay the boot path until the owner runs
aurora-secboot enable. It also makes owner keys, builds the U-Boot Secure
Boot variable seed, moves the Stage 2 key the installer left on the EFI
partition into the encrypted root, and reports the state of the boot chain.

%prep
%autosetup -n aurora-platform-%{commit}

%build
make selinux/aurora_firstboot.pp selinux/aurora_secboot.pp

%install
make install-common install-dracut install-selinux DESTDIR=%{buildroot} PREFIX=%{_prefix}
install -Dm644 /dev/stdin %{buildroot}/usr/lib/systemd/system-preset/90-aurora-firstboot.preset <<'EOF'
enable aurora-firstboot.service
enable aurora-initrd-keymap.path
EOF
make install-power DESTDIR=%{buildroot} PREFIX=%{_prefix} SYSCONFDIR=%{_sysconfdir}
install -Dm644 /dev/stdin %{buildroot}/usr/lib/systemd/system-preset/90-aurora-power-budget.preset <<'EOF'
enable aurora-power-budget.service
enable aurora-power-modes.service
EOF
make install-gamemode DESTDIR=%{buildroot} PREFIX=%{_prefix} SYSCONFDIR=%{_sysconfdir}
make install-secboot install-selinux-secboot DESTDIR=%{buildroot} PREFIX=%{_prefix} SYSCONFDIR=%{_sysconfdir} LOCALSTATEDIR=%{_localstatedir}
install -Dm644 /dev/stdin %{buildroot}/usr/lib/systemd/system-preset/90-aurora-secboot.preset <<'EOF'
enable aurora-secboot-adopt.service
EOF

%post -n aurora-power-budget
%systemd_post aurora-power-budget.service aurora-power-modes.service
# aurora-power-modes is new in 0.1.13-7 and %%systemd_post presets units only
# on a first install: preset it once on the upgrade that brings it, and never
# again, so an administrator's later disable sticks. Where the administrator
# had disabled aurora-power-budget, the new unit stays disabled too.
if [ $1 -gt 1 ] && [ ! -e %{_sharedstatedir}/aurora/power-modes-preset-done ] &&
   systemctl -q is-enabled aurora-power-budget.service 2>/dev/null; then
  systemctl --no-reload preset aurora-power-modes.service >/dev/null 2>&1 || :
fi
mkdir -p %{_sharedstatedir}/aurora && touch %{_sharedstatedir}/aurora/power-modes-preset-done || :
%preun -n aurora-power-budget
%systemd_preun aurora-power-budget.service aurora-power-modes.service
%postun -n aurora-power-budget
%systemd_postun_with_restart aurora-power-budget.service aurora-power-modes.service

%post -n aurora-secboot
# Keep the owner's signing keys away from confined services.
%selinux_modules_install -s %{selinuxtype} %{_datadir}/selinux/packages/%{selinuxtype}/aurora_secboot.pp
%systemd_post aurora-secboot-adopt.service
%preun -n aurora-secboot
%systemd_preun aurora-secboot-adopt.service
%postun -n aurora-secboot
%systemd_postun aurora-secboot-adopt.service
%selinux_modules_uninstall -s %{selinuxtype} aurora_secboot
%posttrans -n aurora-secboot
if selinuxenabled; then
  restorecon -R %{_sharedstatedir}/aurora/secboot || :
fi

%post
# Label the setup programs as ordinary executables so systemd runs them in
# unconfined_service_t, not in its own init_t domain.
%selinux_modules_install -s %{selinuxtype} %{_datadir}/selinux/packages/%{selinuxtype}/aurora_firstboot.pp
%systemd_post aurora-firstboot.service aurora-initrd-keymap.path
%preun
%systemd_preun aurora-firstboot.service aurora-initrd-keymap.path
%postun
# Never restart the account wizard (and its greeter) on upgrade.
%systemd_postun aurora-firstboot.service
%selinux_modules_uninstall -s %{selinuxtype} aurora_firstboot
%posttrans
if selinuxenabled; then
  restorecon -F /usr/lib/aurora/aurora-* || :
fi
# Keep GRUB's lookups on the startup disk on installed Aurora systems.
if [ -f /usr/lib/aurora/image-format ] && mountpoint -q /boot/efi; then
  /usr/lib/aurora/aurora-harden-grub --flavor fedora || :
fi

%transfiletriggerin -- /usr/lib/efi/grub2
# GRUB updates replace EFI/fedora/grub.cfg with a stub that can scan every disk.
if [ -f /usr/lib/aurora/image-format ] && mountpoint -q /boot/efi; then
  /usr/lib/aurora/aurora-harden-grub --flavor fedora || :
fi

%files
%license LICENSE
%{_datadir}/doc/aurora-firstboot/
/usr/lib/aurora/
/usr/lib/dracut/modules.d/97aurora-root/
%{_unitdir}/aurora-firstboot.service
%{_unitdir}/aurora-disk-rekey.service
%{_unitdir}/aurora-initrd-keymap.path
%{_unitdir}/aurora-initrd-keymap.service
%{_unitdir}/display-manager.service.d/aurora-firstboot.conf
%{_unitdir}/getty@.service.d/aurora-firstboot.conf
%{_unitdir}/serial-getty@.service.d/aurora-firstboot.conf
%{_unitdir}/plasma-setup.service.d/aurora-firstboot.conf
%{_unitdir}/plymouth-quit.service.d/aurora-firstboot.conf
%{_unitdir}/systemd-growfs-root.service.d/aurora-growfs.conf
%{_unitdir}/systemd-growfs@.service.d/aurora-growfs.conf
/usr/lib/systemd/system-preset/90-aurora-firstboot.preset
%{_datadir}/selinux/packages/%{selinuxtype}/aurora_firstboot.pp

%files -n aurora-power-budget
%license LICENSE
%{_libexecdir}/aurora/aurora-power-budget
%{_unitdir}/aurora-power-budget.service
%{_libexecdir}/aurora/aurora-power-modes
%{_unitdir}/aurora-power-modes.service
/usr/lib/systemd/system-preset/90-aurora-power-budget.preset
%{_datadir}/doc/aurora-power-budget/
%dir %{_sysconfdir}/aurora
%config(noreplace) %{_sysconfdir}/aurora/power-modes.conf
%dir %{_sharedstatedir}/aurora
%ghost %attr(0644,root,root) %{_sharedstatedir}/aurora/power-modes-preset-done

%files -n aurora-gamemode
%license LICENSE
%config(noreplace) %{_sysconfdir}/gamemode.ini
%{_datadir}/doc/aurora-gamemode/

%files -n aurora-secboot
%license LICENSE
%{_bindir}/aurora-secboot
%{_prefix}/lib/kernel/install.d/92-aurora-secboot.install
%{_unitdir}/aurora-secboot-adopt.service
/usr/lib/systemd/system-preset/90-aurora-secboot.preset
%dir %{_sysconfdir}/aurora
%config(noreplace) %{_sysconfdir}/aurora/secboot.conf
%dir %attr(0700,root,root) %{_sharedstatedir}/aurora/secboot
%{_datadir}/doc/aurora-secboot/
%{_datadir}/selinux/packages/%{selinuxtype}/aurora_secboot.pp

%changelog
* Wed Nov 25 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.13-8
- Refresh to aurora-platform 20c32844.

* Sun Nov 22 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.13-7
- Pin aurora-platform e3bc82ab (aurora-platform#38, carrying #35, on main
  with #33 and #28).
- aurora-power-budget hands each profile to the kernel's apple-clpc
  platform profile and caps the CPU itself only while that does not hold
  Power Saver. tuned-ppd drives only /sys/firmware/acpi/platform_profile,
  which device tree boots lack. When the service stops, a handler it set
  goes back to balanced. apple-clpc registers from the boot loader's Low
  Power ceiling only with a kernel carrying linux 37106688 (#2816); on
  older kernels the CPU budget here applies as before.
- aurora-power-budget also ships aurora-power-modes (enabled by preset,
  once on the upgrade that brings it, and only where aurora-power-budget
  is enabled). In Power Saver it lowers sched_util_clamp_min_rt_default to
  0 and sets the PCIe ASPM policy to powersupersave; every other
  platform-profile handler (apple-smc: High Power mode only) follows the
  profile, unless power-profiles-daemon drives the class itself. #33 keeps
  the boot values as its baseline across a restart. It also adds an
  optional macOS-style "Low Power Mode on battery" setting (default never)
  in /etc/aurora/power-modes.conf, installed with every line commented out.
- On an upgrade from -6 the new unit is enabled but not started (upgrades
  restart only running units): its legs apply from the next boot, or after
  systemctl start aurora-power-modes.

* Tue Nov 17 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.13-6
- New subpackage aurora-gamemode: /etc/gamemode.ini pins games started
  with GameMode to the P cores and keeps schedutil (aurora-platform
  ddf5285). On a MacBook Pro M4 Pro, two frames in flight: geom -9.3 %,
  fill -11.0 % at the same energy per frame. Pulled in automatically
  when gamemode is installed.

* Fri Nov 13 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.13-5
- aurora-secboot gains the "stage2 hook" command that update-m1n1
  20261107-7 calls for every Stage 2 update. With 0.1.13-4 that call failed
  ("invalid choice: stage2"), so update-m1n1 refused every kernel and aura
  update on a system with aurora-secboot installed. The hook returns the
  image unchanged unless the owner's Stage 2 key exists (STAGE2_SIGN=auto).
  Also stage1 build for an owner-key Stage 1 on an existing install, and
  aurora-power-budget stands aside when the kernel budgets power-saver
  itself (aurora-platform ad0411c).

* Thu Nov 12 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.13-4
- New subpackage aurora-secboot: kernel-install builds a unified kernel
  image for each kernel with ukify and signs it with sbsign when the owner's
  db key exists. aurora-secboot enable makes the newest verified image
  EFI/BOOT/BOOTAA64.EFI and keeps shim beside it. The image's command line
  carries lockdown=integrity and none of the shell or lab boot options.
  The aurora_secboot SELinux module labels /var/lib/aurora/secboot as a
  security file type. uki build --os-release names the os-release file
  to embed (aurora-platform 71772a0).

* Sun Nov 08 2026 Aurora Silicon <hey@djdev.me> - 0.1.13-3
- New subpackage aurora-power-budget: Power Saver gets a CPU power budget
  (100 ms, split across clusters from the device tree energy model), as macOS
  Low Power Mode does. Other profiles are untouched (aurora-platform 8fc36c4).

* Tue Nov 03 2026 Aurora Silicon <hey@djdev.me> - 0.1.13-2
- Put aura's Mach-O Stage 1 boot object on the ESP as aurora/stage1.macho,
  for the installer to boot M4 and later Macs from (aurora-platform 6e127f8).

* Mon Nov 02 2026 Aurora Silicon <hey@djdev.me> - 0.1.13-1
- Grow the encrypted root filesystem during the conversion, and run
  systemd-growfs only when a Btrfs filesystem has room to grow. On an
  encrypted root it logged a crypt_resize() error on every boot.
- Refuse to seal a Fedora image whose units differ from their presets.

* Fri Oct 30 2026 Aurora Silicon <hey@djdev.me> - 0.1.12-1
- Give the disk password prompt the system keymap: a console keymap still at
  the image default follows the desktop layout before the password is
  enrolled, a remaining difference is logged, and aurora-initrd-keymap.path
  rebuilds the initrds whenever /etc/vconsole.conf changes.
- Remove the temporary keyslot only on the new password's authority, and
  overwrite every copy of the temporary key and the pre-recovery header
  backup on /boot.
- The PAM hooks do nothing once the disk is rekeyed.

* Thu Oct 29 2026 Aurora Silicon <hey@djdev.me> - 0.1.11-1
- Ask nothing at first boot on desktop images: the owner's account password,
  at its first sign-in, becomes the disk password (aurora-password-hook,
  aurora-disk-rekey.service). On the MacBook Neo the splash stops updating
  once the installed system starts, so a splash prompt was never seen.

* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 0.1.10-1
- Keep systemd status output off the text wizard under show_status=auto, so
  "A start job is running" no longer covers its prompts.

* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 0.1.9-1
- Wait for the root's Btrfs UUID and label devices as long as the unlock
  prompt, so a passphrase typed after 90 seconds no longer fails /sysroot
  into emergency mode.

* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 0.1.8-1
- Create the owner with Plasma Setup or GNOME Initial Setup on desktop images.
  First boot now only protects the disk, with a password chosen on the boot
  splash, and destroys the temporary key before the greeter starts.
- Keep the splash until setup is done, and never take tty1 from Plymouth.
- aurora.firstboot=text starts the text wizard for recovery.

* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 0.1.7-1
- Run the first-boot programs in unconfined_service_t under SELinux through a
  shipped policy module, and label every file setup creates.
- Release the boot splash with a time bound, keep the console clean, retry
  failed steps in place and skip, not fail, the greeter while setup is pending.
- Show the encryption percentage in the splash message.
- Keep GRUB's lookups on the startup disk, also after GRUB updates.
