Name: update-m1n1
Version: 20261107
Release: 1%{?dist}.aurora
Summary: Transactional Aurora Stage 2 updates with retained-kernel DTB checks
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
Source0: update-m1n1
Source1: bootchain.py
Source2: 10-devicetree.install
Source3: 15-update-m1n1.install
Source4: update-m1n1.sysconfig
Source5: LICENSE
Source6: test_bootchain.py
Source7: aurora-stage2-commit
Source8: aurora-stage2-commit.service
Source9: 90-aurora-stage2.preset
Source10: aurora-stage2-guard.service
Source11: aurora-stage2-guard.timer
BuildArch: noarch
BuildRequires: python3 dtc coreutils systemd-rpm-macros
%{?systemd_requires}
Requires: asahi-scripts bash coreutils dtc gzip python3 util-linux
Requires: m1n1 uboot-images-armv8 grubby

%description
Keep the ESP Stage 2 and /boot/dtb unchanged when a retained kernel requires
an older DT ABI generation or has missing device trees. Stage a complete image, sync it, keep
a backup and replace it by rename on older Stage 1 installations. With aura-try,
keep the live image until a successful trial boot. Stage 1 is never changed.

%prep
cp %{SOURCE5} .

%build
python3 -m py_compile %{SOURCE1}

%check
python3 %{SOURCE6}

%install
install -Dm755 %{SOURCE0} %{buildroot}%{_bindir}/update-m1n1
install -Dm644 %{SOURCE1} %{buildroot}%{_libexecdir}/aurora/bootchain.py
# Override grubby's eager link update through kernel-install's supported
# precedence mechanism. Administrator masks and edits remain authoritative.
install -Dm755 %{SOURCE2} %{buildroot}%{_sysconfdir}/kernel/install.d/10-devicetree.install
install -Dm755 %{SOURCE3} %{buildroot}/usr/lib/kernel/install.d/15-update-m1n1.install
install -Dm644 %{SOURCE4} %{buildroot}%{_sysconfdir}/sysconfig/update-m1n1
install -Dm755 %{SOURCE7} %{buildroot}%{_libexecdir}/aurora/aurora-stage2-commit
install -Dm644 %{SOURCE8} %{buildroot}%{_unitdir}/aurora-stage2-commit.service
install -Dm644 %{SOURCE10} %{buildroot}%{_unitdir}/aurora-stage2-guard.service
install -Dm644 %{SOURCE11} %{buildroot}%{_unitdir}/aurora-stage2-guard.timer
install -Dm644 %{SOURCE9} %{buildroot}%{_presetdir}/90-aurora-stage2.preset

%post
%systemd_post aurora-stage2-commit.service aurora-stage2-guard.timer

%preun
%systemd_preun aurora-stage2-commit.service aurora-stage2-guard.timer

%postun
%systemd_postun aurora-stage2-commit.service aurora-stage2-guard.timer

# These units are new to an existing updater installation too. Apply the
# administrator's preset policy exactly once during the vendor transition.
%triggerun -- update-m1n1 < 20261107
/usr/bin/systemctl --no-reload preset aurora-stage2-commit.service aurora-stage2-guard.timer || :

%transfiletriggerin -- /usr/lib/m1n1 /usr/lib64/m1n1 /usr/share/uboot/apple_m1 /etc/m1n1.conf
%{_bindir}/update-m1n1 || :

%files
%license LICENSE
%{_bindir}/update-m1n1
%{_libexecdir}/aurora/bootchain.py
%{_libexecdir}/aurora/aurora-stage2-commit
%{_unitdir}/aurora-stage2-commit.service
%{_unitdir}/aurora-stage2-guard.service
%{_unitdir}/aurora-stage2-guard.timer
%{_presetdir}/90-aurora-stage2.preset
%config(noreplace) %{_sysconfdir}/kernel/install.d/10-devicetree.install
/usr/lib/kernel/install.d/15-update-m1n1.install
%config(noreplace) %{_sysconfdir}/sysconfig/update-m1n1

%changelog
* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261107-1
- Trial the next Stage 2 and commit only after boot-time DT checks.
- Preserve the live image and one attempt per kernel across fallback boots.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261101-2
- Check declared DT ABI generations so routine tree changes can proceed.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261101-1
- Preserve Stage 2 and the DTB link on missing or unproven retained-kernel DTBs.
- Serialize, validate and sync Stage 2 updates and atomically retain the backup.
