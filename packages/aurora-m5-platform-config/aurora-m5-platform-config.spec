Name: aurora-m5-platform-config
Version: 1
Release: 1%{?dist}
Summary: MacBook Pro (M5 Pro) deep sleep configuration
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
Source0: 50-aurora-m5-rtc-safety
Source1: aurora-m5-sleep-policy.service
Source2: 90-aurora-m5-deep.conf
Source3: 90-aurora-m5-lid.conf
Source4: aurora-m5-sleep.conf
Source5: README.md
Source6: LICENSE
BuildArch: noarch
BuildRequires: systemd-rpm-macros
Requires: systemd coreutils grep sed util-linux

%description
Deep sleep on the MacBook Pro (M5 Pro, J714s): suspend is deep sleep only,
the lid suspends on battery, on AC and docked, and a system-sleep hook arms
the PMU RTC safety alarm that the T6050 sleep driver needs. It does nothing
on any other Mac. See README.md.

%prep
cp %{SOURCE5} %{SOURCE6} .

%build

%install
install -Dm755 %{SOURCE0} %{buildroot}%{_systemd_util_dir}/system-sleep/50-aurora-m5-rtc-safety
install -Dm644 %{SOURCE1} %{buildroot}%{_unitdir}/aurora-m5-sleep-policy.service
# Wanted by sysinit.target itself: a preset would not reach Macs that already
# have the package. ConditionFirmware skips every Mac but the J714s.
install -d %{buildroot}%{_unitdir}/sysinit.target.wants
ln -s ../aurora-m5-sleep-policy.service %{buildroot}%{_unitdir}/sysinit.target.wants/aurora-m5-sleep-policy.service
install -Dm644 %{SOURCE2} %{buildroot}%{_datadir}/%{name}/90-aurora-m5-deep.conf
install -Dm644 %{SOURCE3} %{buildroot}%{_datadir}/%{name}/90-aurora-m5-lid.conf
install -Dm644 %{SOURCE4} %{buildroot}%{_sysconfdir}/aurora-m5-sleep.conf

%check
sh -n %{SOURCE0}
grep -q "grep -qx 'apple,j714s' || exit 0" %{SOURCE0}
grep -qx 'ConditionFirmware=device-tree-compatible(apple,j714s)' %{SOURCE1}
grep -qx 'MemorySleepMode=deep' %{SOURCE2}
grep -qx 'HandleLidSwitchDocked=suspend' %{SOURCE3}

%post
# On a running J714s the sleep policy applies from the next suspend; the lid
# setting from the next boot. The unit's condition skips every other Mac.
if [ "$1" -eq 1 ]; then
  systemctl start aurora-m5-sleep-policy.service >/dev/null 2>&1 || :
fi

%files
%license LICENSE
%doc README.md
%{_systemd_util_dir}/system-sleep/50-aurora-m5-rtc-safety
%{_unitdir}/aurora-m5-sleep-policy.service
%{_unitdir}/sysinit.target.wants/aurora-m5-sleep-policy.service
%{_datadir}/%{name}/
%config(noreplace) %{_sysconfdir}/aurora-m5-sleep.conf

%changelog
* Fri Nov 20 2026 Diljit Singh <hey@djdev.me> - 1-1
- Initial package: the MacBook Pro (M5 Pro, J714s) rootfs deep-sleep
  pieces that the M5 deep-sleep gates ran (m5-sleep-root.sh): deep sleep
  only (SuspendState=mem, MemorySleepMode=deep), the lid suspends on
  battery, on AC and docked, and the 50-aurora-m5-rtc-safety hook, which
  arms a 3600 s PMU RTC alarm before a suspend with none armed (the T6050
  sleep driver refuses a sleep without one). Measured on the J714s with
  kernel 7.3.0-m5-intg28d (integration e0ee46a1's tree), switch slot
  sw28d: two rootfs sleeps through logind with this hook, both clean.
  Every other Mac skips the unit, and the hook returns at once.
