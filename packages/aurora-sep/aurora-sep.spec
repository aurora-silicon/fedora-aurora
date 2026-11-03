%global selinuxtype targeted
%global modulename aurora_sep

Name: aurora-sep
Version: 1
Release: 19%{?dist}
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
Source22: authselect-vendor-local
Source23: powerdevilrc
BuildArch: noarch
BuildRequires: systemd-rpm-macros fprintd authselect-libs
BuildRequires: selinux-policy-devel make bzip2
Requires: coreutils fprintd keyutils kmod python3 util-linux grep findutils gawk
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
desktop. A fingerprint or the password unlocks the lock screen and answers
sudo and polkit; the login screen, the console login, su and ssh ask for the
password. A short press of the power button, which is the Touch ID sensor,
suspends.

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
cp -p %{SOURCE3} %{SOURCE4} %{SOURCE19} .
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
install -Dpm0644 %{SOURCE18} %{buildroot}%{_prefix}/lib/systemd/logind.conf.d/50-aurora-sep.conf
install -Dpm0644 %{SOURCE23} %{buildroot}%{_sysconfdir}/xdg/powerdevilrc
# The vendor authselect profile is built at install time from the installed
# authselect (see authselect-vendor-local); list its files as ghosts.
install -Dpm0755 %{SOURCE22} %{buildroot}%{_libexecdir}/aurora/authselect-vendor-local
vendor=%{_datadir}/authselect/vendor/local
install -d %{buildroot}$vendor
# A ghost directory too: an empty vendor profile would hide the default one.
echo "%ghost %dir $vendor" >authselect-vendor.files
for f in %{_datadir}/authselect/default/local/* .aurora-sep; do
    name=${f##*/}
    case $name in
    system-auth|.aurora-sep) touch %{buildroot}$vendor/$name ;;
    *) ln -s $f %{buildroot}$vendor/$name ;;
    esac
    echo "%ghost $vendor/$name" >>authselect-vendor.files
done
grep -qx "%ghost $vendor/system-auth" authselect-vendor.files
grep -qx 'ExecStart=%{_libexecdir}/fprintd' %{_unitdir}/fprintd.service
sed 's|@FPRINTD@|%{_libexecdir}/fprintd|' %{SOURCE7} \
    >%{buildroot}%{_unitdir}/fprintd.service.d/50-aurora-sep-no-timeout.conf
install -d %{buildroot}%{_presetdir}
# The greeter unit is not listed, so it stays off until enabled.
echo 'enable aurora-sep.timer' >%{buildroot}%{_presetdir}/80-aurora-sep.preset
install -Dpm0644 %{modulename}.pp.bz2 \
    %{buildroot}%{_datadir}/selinux/packages/%{selinuxtype}/%{modulename}.pp.bz2

%triggerin -- authselect-libs
# Rebuild the vendor authselect profile from the installed default profile
# whenever either package is installed or updated.
%{_libexecdir}/aurora/authselect-vendor-local || :

%post
%systemd_post aurora-sep.timer aurora-sep.service aurora-sep-ready.service aurora-touchid-setup.service aurora-sep-greeter-fingerprint.service

%preun
%systemd_preun aurora-sep.timer aurora-sep.service aurora-sep-ready.service aurora-touchid-setup.service aurora-sep-greeter-fingerprint.service

%postun
if [ "$1" -eq 0 ] && [ -e %{_sysconfdir}/authselect/authselect.conf ]; then
    # Back to authselect's own profile, as its package does after a profile
    # change; files authselect added since are not ghosts, so remove them too.
    rm -rf %{_datadir}/authselect/vendor/local
    find %{_datadir}/authselect -mindepth 2 -type f -printf '%%P\n' -exec sha256sum {} + |
        sha256sum >%{_datadir}/authselect/checksum 2>/dev/null || :
    authselect apply-changes >/dev/null 2>&1 || :
fi
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
# The loader runs in its own domain from 1-18; label an installed copy now so
# the next boot starts it there.
if selinuxenabled 2>/dev/null && [ -f %{_libexecdir}/aurora-sep-load ]; then
    restorecon %{_libexecdir}/aurora-sep-load || :
fi
# Move the driver's state files from var_lib_t to their own type. Only the
# labels change: the files are never moved, rewritten or removed.
if selinuxenabled 2>/dev/null; then
    for f in /var/lib/apple-sep-catacomb-master.bin \
             /var/lib/apple-sep-catacomb-owner.bin \
             /var/lib/apple-sep-catacomb-user.bin \
             /var/lib/aurora-sep-keybag.bin \
             /var/lib/aurora-sep-refkey.bin \
             /var/lib/aurora-sep-refkey-v2.bin \
             /var/lib/aurora-sep-host-state.bin \
             /var/lib/aurora-sep-xart-owned.bin \
             /var/lib/aurora-sep-xart-allow-once.bin \
             /var/lib/aurora-sep-xart-policy-previous.bin; do
        [ -f "$f" ] && restorecon -F "$f" || :
    done
fi

%files -f authselect-vendor.files
%doc README.md XART-SAFETY.md OS-IDENTITY.md
%{_libexecdir}/aurora-sep-load
%{_libexecdir}/aurora-sep-ready
%{_libexecdir}/aurora-sep-greeter-fingerprint
%{_sbindir}/aurora-touchid-setup
%{_libexecdir}/aurora/touchid-setup-needed
%{_libexecdir}/aurora/extract-mesa-calibration
%{_libexecdir}/aurora/authselect-vendor-local
%{_prefix}/lib/systemd/logind.conf.d/50-aurora-sep.conf
%config(noreplace) %{_sysconfdir}/xdg/powerdevilrc
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
* Tue Nov 03 2026 Aurora Silicon contributors - 1-19
- Offer Touch ID to sudo and polkit as well as the lock screen, and not to the
  console login, su or ssh: authselect's "local" profile is replaced by a
  vendor copy whose system-auth offers a fingerprint only to sudo, sudo-i and
  polkit-1. The copy is rebuilt from the installed authselect whenever either
  package changes, and existing installs regenerate their PAM files.
- Install the logind power-key drop-in instead of shipping it as
  documentation: a short press suspends, a 5 s press powers off.
- Default Plasma's power button to suspend; holding it still opens the logout
  screen.

* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-18
- SELinux: run aurora-sep-load in its own domain, aurora_sep_load_t, with the
  same unconfined access it had as unconfined_service_t. Its probe keys then
  carry that label, and a root process that lists /proc/keys while the probe
  runs (the GDM session worker at an automatic login) is still denied view
  of them, but the denial is no longer logged. This removes the boot AVC on
  Macs where GDM starts before the probe ends.

* Mon Nov 02 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-17
- SELinux: give the driver's state files in /var/lib their own type,
  aurora_sep_state_t, label them so when the kernel creates them, relabel
  existing ones on upgrade, and let fprintd and modprobe use them. Touch ID
  enrolment no longer fails under enforcing with "no durable Catacomb or
  identity-bag binding".
- Turn on authselect's with-fingerprint once on Macs with a sensor, so
  Fingerprint Login shows in GNOME Settings; a later opt-out is kept.

* Sat Oct 31 2026 Aurora Silicon contributors - 1-16
- Rebuild the v4/v5 integration for Fedora 45 alongside Fedora 44

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
