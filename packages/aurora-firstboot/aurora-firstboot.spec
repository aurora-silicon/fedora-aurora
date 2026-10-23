%global commit 5eefa3a93dcebcfb0fe1c3015de2bdaa57e8efe2
%global selinuxtype targeted
Name: aurora-firstboot
Version: 0.1.7
Release: 1%{?dist}
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

%description
Shared first-boot account setup and per-install Btrfs encryption. The image
producer supplies immutable filesystem identities and explicit fresh-image
markers; installing this package alone does not arm encryption or setup.

%prep
%autosetup -n aurora-platform-%{commit}

%build
make selinux/aurora_firstboot.pp

%install
make install-common install-dracut install-selinux DESTDIR=%{buildroot} PREFIX=%{_prefix}
install -Dm644 /dev/stdin %{buildroot}/usr/lib/systemd/system-preset/90-aurora-firstboot.preset <<'EOF'
enable aurora-firstboot.service
EOF

%post
# Label the setup programs as ordinary executables so systemd runs them in
# unconfined_service_t, not in its own init_t domain.
%selinux_modules_install -s %{selinuxtype} %{_datadir}/selinux/packages/%{selinuxtype}/aurora_firstboot.pp
%systemd_post aurora-firstboot.service
%preun
%systemd_preun aurora-firstboot.service
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
%{_unitdir}/display-manager.service.d/aurora-firstboot.conf
%{_unitdir}/getty@.service.d/aurora-firstboot.conf
%{_unitdir}/serial-getty@.service.d/aurora-firstboot.conf
/usr/lib/systemd/system-preset/90-aurora-firstboot.preset
%{_datadir}/selinux/packages/%{selinuxtype}/aurora_firstboot.pp

%changelog
* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 0.1.7-1
- Run the first-boot programs in unconfined_service_t under SELinux through a
  shipped policy module, and label every file setup creates.
- Release the boot splash with a time bound, keep the console clean, retry
  failed steps in place and skip, not fail, the greeter while setup is pending.
- Show the encryption percentage in the splash message.
- Keep GRUB's lookups on the startup disk, also after GRUB updates.
