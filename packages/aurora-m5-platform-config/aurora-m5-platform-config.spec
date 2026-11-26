Name: aurora-m5-platform-config
Version: 1
Release: 3%{?dist}
Summary: Lid policy for kernel-selected deep sleep
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
Source0: aurora-m5-sleep-policy.service
Source1: 90-aurora-m5-lid.conf
Source2: README.md
Source3: LICENSE
BuildArch: noarch
BuildRequires: systemd-rpm-macros
Requires: systemd coreutils grep

%description
Configure logind to suspend on lid close when the kernel selects deep sleep.
Logind applies the settings to systems reporting a lid switch.

%prep
cp %{SOURCE2} %{SOURCE3} .

%build

%install
install -Dm644 %{SOURCE0} %{buildroot}%{_unitdir}/aurora-m5-sleep-policy.service
# The sysinit dependency also reaches systems that already have the package.
install -d %{buildroot}%{_unitdir}/sysinit.target.wants
ln -s ../aurora-m5-sleep-policy.service %{buildroot}%{_unitdir}/sysinit.target.wants/aurora-m5-sleep-policy.service
install -Dm644 %{SOURCE1} %{buildroot}%{_datadir}/%{name}/90-aurora-m5-lid.conf

%check
grep -Fxq 'RemainAfterExit=yes' %{SOURCE0}
grep -Fq 'grep -Fq "[deep]" /sys/power/mem_sleep' %{SOURCE0}
grep -Fxq 'HandleLidSwitchDocked=suspend' %{SOURCE1}

%post
# Logind reads the lid policy on its next start.
if [ "$1" -eq 1 ]; then
  systemctl start aurora-m5-sleep-policy.service >/dev/null 2>&1 || :
fi

%files
%license LICENSE
%doc README.md
%{_unitdir}/aurora-m5-sleep-policy.service
%{_unitdir}/sysinit.target.wants/aurora-m5-sleep-policy.service
%{_datadir}/%{name}/

%changelog
* Wed Nov 25 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-3
- Complete the boot unit without installing a policy on s2idle kernels.
* Wed Nov 25 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-2
- Follow the kernel-selected deep sleep mode and logind lid detection.
- Drop the superseded automatic RTC alarm and sleep-mode override.
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
