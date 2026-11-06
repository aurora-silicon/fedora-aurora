# Fedora's update-m1n1 with Aurora's Mach-O handling: once aura has no monitor,
# those Macs get m1n1/boot-ctxr.bin and m1n1/boot.bin stays as it is. The script
# is asahi-scripts 20261023's with Fedora's dangling /boot/dtb fix. Fedora's
# other asahi-scripts subpackages stay Fedora's.
Name: update-m1n1
Version: 20261023
Release: 1%{?dist}
Summary: Keep the ESP Stage 2 up to date
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
Source0: update-m1n1
Source1: update-m1n1.sysconfig
Source2: 15-update-m1n1.install
BuildRequires: systemd-rpm-macros
Requires: asahi-scripts
Requires: bash
Requires: coreutils
Requires: gzip
Requires: m1n1
Requires: uboot-images-armv8
# grubby's /usr/lib/kernel/install.d/10-devicetree.install creates the
# /boot/dtb symlink this uses to construct the Stage 2 image.
Requires: grubby
# aura requires this: an aura without the monitor must never reach boot.bin.
Provides: aurora-stage2-ctxr-slot = 1

%description
Writes aura, the kernel's device trees and U-Boot into the ESP Stage 2 on kernel,
aura and U-Boot updates, keeping the previous file for rollback. Once aura has no
monitor, a Mac that boots a Mach-O Stage 1 gets only its own device trees, in
m1n1/boot-ctxr.bin.

%prep
%build

%install
install -Dpm0755 %{SOURCE0} %{buildroot}%{_sbindir}/update-m1n1
install -Dpm0644 %{SOURCE1} %{buildroot}%{_sysconfdir}/sysconfig/update-m1n1
install -Dpm0755 -t %{buildroot}%{_kernel_install_dir} %{SOURCE2}

# We can't use _libdir here because it gets incorrectly expanded to /usr/lib
%transfiletriggerin -- /usr/lib/m1n1 /usr/lib64/m1n1 /usr/share/uboot/apple_m1 /etc/m1n1.conf
%{_sbindir}/update-m1n1 || :

%files
%config(noreplace) %{_sysconfdir}/sysconfig/update-m1n1
%{_kernel_install_dir}/15-update-m1n1.install
%{_sbindir}/update-m1n1

%changelog
* Fri Nov 06 2026 Diljit Singh <hey@djdev.me> - 20261023-1
- Take over Fedora's update-m1n1. Once the aura package marks itself as having
  no monitor, a Mac that boots a Mach-O Stage 1 gets m1n1/boot-ctxr.bin with only
  that board's device trees, and m1n1/boot.bin stays as it is.
