%global commit 8fc36c44f7353c7c1c0ffa3aff3ae0aa69f9ce54
%global selinuxtype targeted
Name: aurora-firstboot
Version: 0.1.13
Release: 3%{?dist}
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
Mode: every 100 ms the budget is split across the CPU clusters by demand,
using the device tree energy model, and each cluster is capped to its share.
Balanced and Performance are untouched.

%prep
%autosetup -n aurora-platform-%{commit}

%build
make selinux/aurora_firstboot.pp

%install
make install-common install-dracut install-selinux DESTDIR=%{buildroot} PREFIX=%{_prefix}
install -Dm644 /dev/stdin %{buildroot}/usr/lib/systemd/system-preset/90-aurora-firstboot.preset <<'EOF'
enable aurora-firstboot.service
enable aurora-initrd-keymap.path
EOF
make install-power DESTDIR=%{buildroot} PREFIX=%{_prefix}
install -Dm644 /dev/stdin %{buildroot}/usr/lib/systemd/system-preset/90-aurora-power-budget.preset <<'EOF'
enable aurora-power-budget.service
EOF

%post -n aurora-power-budget
%systemd_post aurora-power-budget.service
%preun -n aurora-power-budget
%systemd_preun aurora-power-budget.service
%postun -n aurora-power-budget
%systemd_postun_with_restart aurora-power-budget.service

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
/usr/lib/systemd/system-preset/90-aurora-power-budget.preset
%{_datadir}/doc/aurora-power-budget/

%changelog
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
