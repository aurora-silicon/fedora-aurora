Name: aurora-sep
Version: 1
Release: 7%{?dist}
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
Source8: prepare-sep-calibration
Source9: extract-mesa-calibration
Source10: 90-aurora-sep.conf
Source11: aurora-sep.timer
Source12: aurora-sep-load.conf
Source13: aurora_sep.te
Source14: aurora_sep.fc
Source15: sensor-present
BuildArch: noarch
BuildRequires: systemd-rpm-macros fprintd
BuildRequires: selinux-policy-devel make bzip2
Requires: coreutils fprintd keyutils kmod python3 util-linux grep
Requires: libfprint(aurora-sep) = 4
Requires: kernel-aurora-core >= 7.2.10-5
%{?systemd_requires}
%{?selinux_requires_min}
Requires(postun): libselinux-utils policycoreutils
Requires(posttrans): policycoreutils

%description
Loads the SEP module after persistent storage is mounted and verifies trusted
key sealing and unsealing. On machines with a fingerprint reader, the package
also prepares per-device calibration and lets fprintd use the Aurora libfprint
driver. Initialization runs in the background without holding up the desktop.
Password authentication policy is unchanged.

%prep
%setup -q -c -T
cp -p %{SOURCE3} %{SOURCE4} .
cp -p %{SOURCE13} %{SOURCE14} .

%build
%make_build -f %{_datadir}/selinux/devel/Makefile aurora_sep.pp
bzip2 -9 aurora_sep.pp

%install
unit() {
    install -Dpm0755 "$1" %{buildroot}%{_libexecdir}/"$3"
    install -Dpm0644 "$2" %{buildroot}%{_unitdir}/"${2##*/}"
    sed -i "s|/usr/local/sbin/$3|%{_libexecdir}/$3|" %{buildroot}%{_unitdir}/"${2##*/}"
    if grep -q /usr/local %{buildroot}%{_unitdir}/"${2##*/}"; then exit 1; fi
}
unit %{SOURCE0} %{SOURCE1} aurora-sep-load
unit %{SOURCE5} %{SOURCE6} aurora-sep-ready
install -Dpm0644 %{SOURCE11} %{buildroot}%{_unitdir}/aurora-sep.timer
install -Dpm0644 %{SOURCE12} %{buildroot}%{_prefix}/lib/modprobe.d/aurora-sep-load.conf
install -Dpm0755 %{SOURCE8} %{buildroot}%{_libexecdir}/aurora/prepare-sep-calibration
install -Dpm0755 %{SOURCE9} %{buildroot}%{_libexecdir}/aurora/extract-mesa-calibration
install -Dpm0755 %{SOURCE15} %{buildroot}%{_libexecdir}/aurora-sep-sensor-present
install -Dpm0644 %{SOURCE10} %{buildroot}%{_prefix}/lib/dracut/dracut.conf.d/90-aurora-sep.conf
install -Dpm0644 %{SOURCE2} %{buildroot}%{_unitdir}/fprintd.service.d/aurora-sep.conf
grep -qx 'ExecStart=%{_libexecdir}/fprintd' %{_unitdir}/fprintd.service
sed 's|@FPRINTD@|%{_libexecdir}/fprintd|' %{SOURCE7} \
    >%{buildroot}%{_unitdir}/fprintd.service.d/50-aurora-sep-no-timeout.conf
install -d %{buildroot}%{_presetdir}
echo 'enable aurora-sep.timer' >%{buildroot}%{_presetdir}/80-aurora-sep.preset
install -Dpm0644 aurora_sep.pp.bz2 %{buildroot}%{_datadir}/selinux/packages/targeted/aurora_sep.pp.bz2

%post
%selinux_modules_install -s targeted %{_datadir}/selinux/packages/targeted/aurora_sep.pp.bz2
%systemd_post aurora-sep.timer aurora-sep.service aurora-sep-ready.service

%preun
%systemd_preun aurora-sep.timer aurora-sep.service aurora-sep-ready.service

%postun
# The handoff is once per boot, so do not restart the loader on upgrade.
%systemd_postun aurora-sep.timer aurora-sep.service aurora-sep-ready.service
%selinux_modules_uninstall -s targeted aurora_sep
if [ "$1" -eq 0 ] && [ -e /dev/sep-bio ]; then
    restorecon /dev/sep-bio || :
fi

%posttrans
if [ -e /dev/sep-bio ]; then
    restorecon /dev/sep-bio || :
fi

%files
%doc README.md XART-SAFETY.md
%{_libexecdir}/aurora-sep-load
%{_libexecdir}/aurora-sep-ready
%{_libexecdir}/aurora/prepare-sep-calibration
%{_libexecdir}/aurora/extract-mesa-calibration
%{_libexecdir}/aurora-sep-sensor-present
%{_prefix}/lib/dracut/dracut.conf.d/90-aurora-sep.conf
%{_prefix}/lib/modprobe.d/aurora-sep-load.conf
%{_unitdir}/aurora-sep.service
%{_unitdir}/aurora-sep-ready.service
%{_unitdir}/aurora-sep.timer
%dir %{_unitdir}/fprintd.service.d
%{_unitdir}/fprintd.service.d/aurora-sep.conf
%{_unitdir}/fprintd.service.d/50-aurora-sep-no-timeout.conf
%{_presetdir}/80-aurora-sep.preset
%{_datadir}/selinux/packages/targeted/aurora_sep.pp.bz2

%changelog
* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 1-6
- Label the SEP biometric device and permit fprintd access under SELinux

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 1-5
- Wait for the modular running kernel during an upgrade

* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 1-4
- Initialize SEP from the mounted root and prepare local calibration
