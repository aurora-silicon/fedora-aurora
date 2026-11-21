Name: update-m1n1
Version: 20261107
Release: 12%{?dist}.aurora
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
Source12: kernel-install-repair
Provides: aurora-stage2-ctxr-slot = 1
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
install -Dpm0755 %{SOURCE0} %{buildroot}%{_sbindir}/update-m1n1
install -Dm644 %{SOURCE1} %{buildroot}%{_libexecdir}/aurora/bootchain.py
# Override grubby's eager link update through kernel-install's supported
# precedence mechanism. Administrator masks and edits remain authoritative.
install -Dm755 %{SOURCE2} %{buildroot}%{_sysconfdir}/kernel/install.d/10-devicetree.install
install -Dm755 %{SOURCE3} %{buildroot}%{_kernel_install_dir}/15-update-m1n1.install
install -Dm644 %{SOURCE4} %{buildroot}%{_sysconfdir}/sysconfig/update-m1n1
install -Dm755 %{SOURCE7} %{buildroot}%{_libexecdir}/aurora/aurora-stage2-commit
install -Dm755 %{SOURCE12} %{buildroot}%{_libexecdir}/aurora/kernel-install-repair
install -Dm644 %{SOURCE8} %{buildroot}%{_unitdir}/aurora-stage2-commit.service
install -Dm644 %{SOURCE10} %{buildroot}%{_unitdir}/aurora-stage2-guard.service
install -Dm644 %{SOURCE11} %{buildroot}%{_unitdir}/aurora-stage2-guard.timer
install -Dm644 %{SOURCE9} %{buildroot}%{_presetdir}/90-aurora-stage2.preset
# bootchain.py hands each Stage 2 to "aurora-secboot stage2 hook"; aurora-secboot stage1 build --enforce
# looks for this marker before it builds a Stage 1 that refuses unsigned Stage 2s.
install -Dm644 /dev/null %{buildroot}%{_datadir}/aurora/stage2-sign-hook

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

# A kernel added while an older updater refused it has no boot entry yet.
%posttrans
%{_libexecdir}/aurora/kernel-install-repair || :

%transfiletriggerin -- /usr/lib/m1n1 /usr/lib64/m1n1 /usr/share/uboot/apple_m1 /etc/m1n1.conf
%{_sbindir}/update-m1n1 || :

# A transaction runs kernel-install remove for every kernel it erases, also
# for one it reinstalls, before the kernels it installs are added. Record the
# transaction before it starts: its removals then leave Stage 2 to the kernels
# it adds and to a refresh after it, which follows what GRUB boots next.
%transfiletriggerun -- /usr/lib/modules
AURORA_RPM_TRANSACTION_PID=$PPID %{_sbindir}/update-m1n1 --transaction-begin || :

%transfiletriggerpostun -- /usr/lib/modules
%{_sbindir}/update-m1n1 --transaction-end || :

%transfiletriggerin -- /usr/lib/modules
%{_sbindir}/update-m1n1 --transaction-end || :

%files
%license LICENSE
%{_sbindir}/update-m1n1
%{_libexecdir}/aurora/bootchain.py
%{_libexecdir}/aurora/aurora-stage2-commit
%{_libexecdir}/aurora/kernel-install-repair
%{_unitdir}/aurora-stage2-commit.service
%{_unitdir}/aurora-stage2-guard.service
%{_unitdir}/aurora-stage2-guard.timer
%{_presetdir}/90-aurora-stage2.preset
%{_datadir}/aurora/stage2-sign-hook
%config(noreplace) %{_sysconfdir}/kernel/install.d/10-devicetree.install
%{_kernel_install_dir}/15-update-m1n1.install
%config(noreplace) %{_sysconfdir}/sysconfig/update-m1n1

%changelog
* Fri Nov 20 2026 Diljit Singh <hey@djdev.me> - 20261107-12
- Write Stage 2 only to the file this boot's Stage 1 loads (#452). A
  kernel-install on a J713 whose lab Stage 1 loads aura/stage2.bin
  armed a trial of the packaged, older Stage 2 at m1n1/boot-ctxr.bin.next:
  the next boot would have run it, and its commit would have replaced a
  file that Stage 1 never reads. A Stage 1 from aura 1.0.0b12 on
  records the SHA-256 of the image it loaded; the target, without its
  aura_sig trailer, must match it. An older Stage 1 with aura-try must
  have booted the Stage 2 version the target carries. Otherwise the ESP
  is left alone, the hook still succeeds so the kernel installs, and it
  says which file Stage 1 loads.
- Never install an aura release older than the running Stage 2, unless
  AURORA_STAGE2_ALLOW_DOWNGRADE=1 is set for that run.
- Withdraw a trial this updater armed that never booted and fails
  either check.
- Read 1.0.0b13.1-style point releases as aura versions with aura-try,
  and aura#313's aurora,aura-stage{1,2}-version names.

* Sun Nov 15 2026 Isaac Duarte <31712685+Isaac-Duarte@users.noreply.github.com> - 20261107-9
- Find the node a display alias names by its exact path. fdtget resolves
  a component without a unit address, such as /soc, to the first soc@...
  sibling, so on T6050 trees (soc@200000000, soc@2308000000 and soc) a
  DCP under the plain soc looked missing and Stage 2 trials were refused.

* Sun Nov 15 2026 Diljit Singh <hey@djdev.me> - 20261107-8
- A reinstall of the GRUB default kernel no longer arms a Stage 2 trial
  with another kernel's device trees. dnf runs kernel-install remove for
  the old instance before it adds the kernel again, and that removal
  armed a trial for the newest remaining kernel, which the add left
  armed. Kernel removals inside a package transaction now leave Stage 2
  to the kernels the transaction adds and to a refresh after it, which
  RPM file triggers on /usr/lib/modules run.
- Withdraw an armed trial that was never booted when the Stage 2 for the
  kernel GRUB boots is already live, or when the trial was armed for
  another kernel. Its candidate may be armed again later; one that fell
  back is still never rearmed.
- When GRUB's default is unknown or removed, compose from GRUB's first
  boot entry in GRUB's own order, not from the version-sorted newest
  kernel. Local kernels such as 7.3.0-neo.1 sorted above every release.

* Fri Nov 13 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261107-7
- Hand each composed Stage 2 to aurora-secboot's stage2 hook when it is
  installed, so an owner-key Stage 1 gets a Stage 2 signed with the
  owner's key; a signing failure keeps the last Stage 2. Ship the
  stage2-sign-hook marker that aurora-secboot stage1 build checks.

* Mon Nov 09 2026 Diljit Singh <hey@djdev.me> - 20261107-6
- Stop stranding Macs on an old kernel. A refused Stage 2 update failed
  15-update-m1n1.install, so kernel-install stopped before the new
  kernel's initramfs and boot entry and the Mac kept booting the old one.
  A J493 stayed on 7.3.0-20, whose speakers no daemon can unlock, while
  7.3.0-26 and -27 were installed. Two refusals did it:
  - A boot entry whose kernel is gone (an Asahi kernel removed on
    migration) is ignored, with a message: GRUB cannot boot it. An entry
    whose kernel exists elsewhere, or that names none, still refuses.
  - A kernel without a dtb-abi marker counts as generation 1, not 0. The
    first declaration changed no device tree, and those kernels booted
    the trees that followed. Generation 2 still refuses them.
- kernel-install-repair, run from %%posttrans, re-runs kernel-install for
  each kernel-aurora-core newer than every kernel with a boot entry, so a
  stranded Mac boots its newest kernel after this update.

* Mon Nov 09 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261107-5
- aurora-stage2-commit skips a trial it did not arm. When the aura-try
  marker names another image (a trial armed by hand or by another tool),
  the service logs that and exits 0, leaving the marker and image alone.
  It used to fail the unit with "another aura-try owns the ESP marker".

* Mon Nov 09 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261107-4
- Compose Stage 2 from the kernel GRUB boots by default (custom.cfg
  `set default`, GRUB_DEFAULT, or grubenv saved_entry) instead of the
  newest installed kernel. A leftover test kernel that sorts above the
  default no longer decides the live DTB set. A new kernel is still used
  when kernel-install will make it the default (UPDATEDEFAULT=yes and no
  custom.cfg pin). Unknown defaults keep the newest kernel, as GRUB does.

* Sun Nov 08 2026 Diljit Singh <hey@djdev.me> - 20261107-3
- Image builds: with no device tree and no target, stop after the check.
  The image builder writes Stage 2; mounting a system ESP there failed the
  kernel transaction and every image build.

* Sun Nov 08 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261107-2
- Record one trial attempt per Stage 2 candidate (sha256), not per kernel, so
  aura, U-Boot and m1n1.conf updates on the same kernel are trialled too.
- Mark committed attempts; never rearm a candidate that fell back.
- Treat a trial boot as ordinary once its commit has replaced the live image.

* Sat Nov 07 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261107-1
- Trial the next Stage 2 and commit only after boot-time DT checks.
- Preserve the live image and one attempt per kernel across fallback boots.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261101-2
- Check declared DT ABI generations so routine tree changes can proceed.

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 20261101-1
- Preserve Stage 2 and the DTB link on missing or unproven retained-kernel DTBs.
- Serialize, validate and sync Stage 2 updates and atomically retain the backup.
