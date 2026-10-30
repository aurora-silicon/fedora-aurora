%global selinuxtype targeted
%global modulename aurora_sep

Name: aurora-sep
Version: 1
Release: 15%{?dist}
Summary: SEP trusted-key and fingerprint integration for Aurora
License: GPL-2.0-only
URL: https://github.com/aurora-silicon/linux
Source0: load-driver
Source1: aurora-sep.service
Source2: fprintd-aurora.conf
Source3: README.md
Source4: XART-SAFETY.md
Source5: aurora-sep-ready
Source6: aurora-sep-ready.service
Source7: fprintd-no-timeout.conf.in
Source8: aurora-touchid-setup
Source9: extract-mesa-calibration
Source10: 90-aurora-sep.conf
Source11: aurora-sep.timer
Source12: aurora-sep-load.conf
Source13: aurora_sep.te
Source14: aurora_sep.fc
Source15: sensor-present
Source16: aurora-sep-greeter-fingerprint
Source17: aurora-sep-greeter-fingerprint.service
Source18: logind-aurora-sep.conf
Source19: OS-IDENTITY.md
Source20: aurora-touchid-setup.service
Source21: touchid-setup-needed
BuildArch: noarch
BuildRequires: systemd-rpm-macros fprintd
BuildRequires: selinux-policy-devel make bzip2
Requires: coreutils fprintd keyutils kmod python3 util-linux grep
Requires: libfprint(aurora-sep) = 5
Requires: fprintd(aurora-sep) = 1
# Holds the packaged kernel to one with the module-based SEP driver, and
# leaves a kernel installed outside RPM alone; the units skip a kernel
# without a loadable apple_sep.
Requires: (kernel-aurora-core >= 7.2.10-5 if kernel-aurora-core)
Requires: (%{name}-selinux = %{version}-%{release} if selinux-policy-%{selinuxtype})
# Only for aurora-sep-greeter-fingerprint.service, which is off by default.
Suggests: /usr/bin/gresource
%{?systemd_requires}

%description
Loads the SEP module after persistent storage is mounted and verifies trusted
key sealing and unsealing. On machines with a fingerprint reader, the package
also prepares per-device calibration, activates Touch ID before fprintd starts
and lets fprintd use the Aurora libfprint driver. Touch ID is reported ready
only when the sensor attached, the fingerprints were restored and a match can
save its state. Initialization runs in the background without holding up the
desktop. Password authentication and power-button policy are unchanged.

%package selinux
Summary: SELinux policy module for the Apple SEP fingerprint device
Requires: selinux-policy-%{selinuxtype}
Requires(post): selinux-policy-%{selinuxtype}
Requires(post): policycoreutils
Requires(postun): libselinux-utils policycoreutils
%{?selinux_requires}

%description selinux
Labels /dev/sep-bio, the Apple SEP driver's Touch ID device, and lets fprintd
open it and read the lid switch from input event devices. The units' helpers
may open and query the device. The targeted policy otherwise leaves the
device as device_t, which fprintd may not open.

%prep
%setup -q -c -T
cp -p %{SOURCE3} %{SOURCE4} %{SOURCE19} %{SOURCE18} .
cp -p %{SOURCE13} %{SOURCE14} .

%build
%make_build -f %{_datadir}/selinux/devel/Makefile %{modulename}.pp
bzip2 -9 %{modulename}.pp

%install
unit() {
    install -Dpm0755 "$1" %{buildroot}%{_libexecdir}/"$3"
    install -Dpm0644 "$2" %{buildroot}%{_unitdir}/"${2##*/}"
    sed -i "s|/usr/local/sbin/$3|%{_libexecdir}/$3|" %{buildroot}%{_unitdir}/"${2##*/}"
    if grep -q /usr/local %{buildroot}%{_unitdir}/"${2##*/}"; then exit 1; fi
}
unit %{SOURCE0} %{SOURCE1} aurora-sep-load
unit %{SOURCE5} %{SOURCE6} aurora-sep-ready
unit %{SOURCE16} %{SOURCE17} aurora-sep-greeter-fingerprint
install -Dpm0644 %{SOURCE11} %{buildroot}%{_unitdir}/aurora-sep.timer
install -Dpm0644 %{SOURCE12} %{buildroot}%{_prefix}/lib/modprobe.d/aurora-sep-load.conf
install -Dpm0755 %{SOURCE8} %{buildroot}%{_sbindir}/aurora-touchid-setup
install -Dpm0755 %{SOURCE21} %{buildroot}%{_libexecdir}/aurora/touchid-setup-needed
install -Dpm0644 %{SOURCE20} %{buildroot}%{_unitdir}/aurora-touchid-setup.service
sed -i 's|^ExecStart=/usr/sbin/|ExecStart=%{_sbindir}/|' %{buildroot}%{_unitdir}/aurora-touchid-setup.service
install -Dpm0755 %{SOURCE9} %{buildroot}%{_libexecdir}/aurora/extract-mesa-calibration
install -Dpm0755 %{SOURCE15} %{buildroot}%{_libexecdir}/aurora-sep-sensor-present
install -Dpm0644 %{SOURCE10} %{buildroot}%{_prefix}/lib/dracut/dracut.conf.d/90-aurora-sep.conf
install -Dpm0644 %{SOURCE2} %{buildroot}%{_unitdir}/fprintd.service.d/aurora-sep.conf
grep -qx 'ExecStart=%{_libexecdir}/fprintd' %{_unitdir}/fprintd.service
sed 's|@FPRINTD@|%{_libexecdir}/fprintd|' %{SOURCE7} \
    >%{buildroot}%{_unitdir}/fprintd.service.d/50-aurora-sep-no-timeout.conf
install -d %{buildroot}%{_presetdir}
# The greeter unit is not listed, so it stays off until enabled.
echo 'enable aurora-sep.timer' >%{buildroot}%{_presetdir}/80-aurora-sep.preset
install -Dpm0644 %{modulename}.pp.bz2 \
    %{buildroot}%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2

%post
%systemd_post aurora-sep.timer aurora-sep.service aurora-sep-ready.service aurora-touchid-setup.service aurora-sep-greeter-fingerprint.service

%preun
%systemd_preun aurora-sep.timer aurora-sep.service aurora-sep-ready.service aurora-touchid-setup.service aurora-sep-greeter-fingerprint.service

%postun
# The handoff is once per boot, so do not restart the loader on upgrade.
%systemd_postun aurora-sep.timer aurora-sep.service aurora-sep-ready.service aurora-touchid-setup.service aurora-sep-greeter-fingerprint.service

%pre selinux
%selinux_relabel_pre -s %{selinuxtype}

%post selinux
%selinux_modules_install -s %{selinuxtype} %{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2

%postun selinux
%selinux_modules_uninstall -s %{selinuxtype} %{modulename}
if [ "$1" -eq 0 ] && selinuxenabled 2>/dev/null && [ -c /dev/sep-bio ]; then
    restorecon /dev/sep-bio || :
fi

%posttrans selinux
%selinux_relabel_post -s %{selinuxtype}
# udev labels the device when the driver creates it; label one that exists.
if selinuxenabled 2>/dev/null && [ -c /dev/sep-bio ]; then
    restorecon /dev/sep-bio || :
fi

%files
%doc README.md XART-SAFETY.md OS-IDENTITY.md logind-aurora-sep.conf
%{_libexecdir}/aurora-sep-load
%{_libexecdir}/aurora-sep-ready
%{_libexecdir}/aurora-sep-greeter-fingerprint
%{_sbindir}/aurora-touchid-setup
%{_libexecdir}/aurora/touchid-setup-needed
%{_libexecdir}/aurora/extract-mesa-calibration
%{_libexecdir}/aurora-sep-sensor-present
%{_prefix}/lib/dracut/dracut.conf.d/90-aurora-sep.conf
%{_prefix}/lib/modprobe.d/aurora-sep-load.conf
%{_unitdir}/aurora-sep.service
%{_unitdir}/aurora-sep-ready.service
%{_unitdir}/aurora-touchid-setup.service
%{_unitdir}/aurora-sep-greeter-fingerprint.service
%{_unitdir}/aurora-sep.timer
%dir %{_unitdir}/fprintd.service.d
%{_unitdir}/fprintd.service.d/aurora-sep.conf
%{_unitdir}/fprintd.service.d/50-aurora-sep-no-timeout.conf
%{_presetdir}/80-aurora-sep.preset

%files selinux
%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2
%ghost %verify(not md5 size mode mtime) %{_sharedstatedir}/selinux/%{selinuxtype}/active/modules/200/%{modulename}

%changelog
* Fri Oct 30 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-14
- Replace the every-boot prepare-sep-calibration with aurora-touchid-setup,
  which runs only when a Touch ID file is missing, when the enclave refused
  one this boot (once per boot, started by aurora-sep-ready), or by hand,
  with --check and --force-rebuild
- Rebuild the sealed calibration and the sensor's signed root key from the
  Mac's factory records on the Hardware volume (Erik Bourget's reader), and
  install a carved comb record as it is on M1 and M2
- Read the fingerprint firmware-name list as the driver does: the first
  entry is the calibration and the second the sensor's root key

* Fri Oct 30 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-13
- prepare-sep-calibration reads the fingerprint firmware-name as a list and
  takes the calibration entry, so the J616s, which also names its MSRk
  record, gets its calibration again

* Fri Oct 30 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-12
- Wait for the enclave bring-up before the trusted-key probe, so the probe no
  longer holds the kernel key lock and stalls every service start at boot

* Fri Oct 30 2026 Aurora Silicon <ryan@aurorasilicon.org> - 1-11
- prepare-sep-calibration installs only a comb record and only over a file
  it installed: a standalone FSC2 image is no longer written over the sealed
  calibration on the MacBook Neo, where the enclave refused it (0x1c)
- Release 11 stays above the linux tree's kit spec at 1-10

* Thu Oct 29 2026 Aurora Silicon <ryan@aurorasilicon.org> - 1-9
- Update to tools/aurora-sep from aurora-silicon/linux integration/aurora:
  Touch ID is ready only once the sensor attached, the fingerprints were
  restored and the xART guard lets a match save its state, with the reason
  when it is not
- Ship the opt-in GNOME login screen fingerprint unit, off by default, and
  the logind power-button snippet as documentation only
- Move the policy module to aurora-sep-selinux, which upgrades the one the
  linux tree built, and use the same policy text as that tree
- Require kernel-aurora-core only when it is installed, so the package also
  installs beside a kernel from outside RPM

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 1-6
- Label the SEP biometric device and permit fprintd access under SELinux

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 1-5
- Wait for the modular running kernel during an upgrade

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 1-4
- Initialize SEP from the mounted root and prepare local calibration
