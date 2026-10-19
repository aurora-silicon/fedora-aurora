%global commit fbcbf053ba5c5fd9d18c62ed8abecc85b0ca795f
Name: aurora-firstboot
Version: 0.1.4
Release: 3%{?dist}
Summary: Aurora per-install root encryption and Linux account setup
License: MIT
URL: https://github.com/aurora-silicon/aurora-platform
Source0: aurora-firstboot-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: make systemd-rpm-macros
Requires: bash cryptsetup >= 2.8 btrfs-progs util-linux coreutils systemd python3 shadow-utils sudo kbd
Requires: dracut policycoreutils selinux-policy-targeted

%description
Shared first-boot account setup and per-install Btrfs encryption. The image
producer supplies immutable filesystem identities and explicit fresh-image
markers; installing this package alone does not arm encryption or setup.

%prep
%autosetup -n aurora-platform-%{commit}

%build

%install
make install-common install-dracut DESTDIR=%{buildroot} PREFIX=%{_prefix}
install -Dm644 /dev/stdin %{buildroot}/usr/lib/systemd/system-preset/90-aurora-firstboot.preset <<'EOF'
enable aurora-firstboot.service
EOF

%post
%systemd_post aurora-firstboot.service
%preun
%systemd_preun aurora-firstboot.service
%postun
%systemd_postun_with_restart aurora-firstboot.service

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
