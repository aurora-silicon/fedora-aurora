%global commit e03febfe52a540e9255036a01e18030e0a5135f9
Name: speakerguardd
Version: 0.1.0
Release: 3%{?dist}
Summary: Feed-forward speaker protection for Apple J700
License: MIT
URL: https://github.com/aurora-silicon/speakerguardd
Source0: speakerguardd-%{commit}.tar.gz
Source1: use-feedback-guard
Source2: 50-j700-guard.conf
ExclusiveArch: aarch64
BuildRequires: rust cargo alsa-lib-devel pkgconf-pkg-config systemd-rpm-macros

%description
Feed-forward speaker protection for Apple J700. Built from the recorded Aurora source revision.

%prep
%autosetup -n speakerguardd-e03febfe52a540e9255036a01e18030e0a5135f9

%build
cargo build --locked --release

%check
cargo test --locked

%install
install -Dm755 target/release/speakerguardd %{buildroot}%{_bindir}/speakerguardd
mkdir -p %{buildroot}%{_datadir}/speakerguardd
cp -a conf/. %{buildroot}%{_datadir}/speakerguardd/
install -Dm644 speakerguardd.service %{buildroot}%{_unitdir}/speakerguardd.service
sed -i 's@ExecStart=/usr/bin/speakerguardd -c /usr/share/speakerguardd@ExecStart=/usr/bin/speakerguardd -c /usr/share/speakerguardd -C AppleJ700@' %{buildroot}%{_unitdir}/speakerguardd.service
sed -i '/^StartLimitInterval=60$/d; /^StartLimitBurst=10$/d; /Description=Speaker Protection Daemon (feed-forward)/a StartLimitIntervalSec=60\nStartLimitBurst=10' %{buildroot}%{_unitdir}/speakerguardd.service
install -Dm644 95-speakerguardd.rules %{buildroot}%{_udevrulesdir}/95-speakerguardd.rules
install -Dm755 %{SOURCE1} %{buildroot}%{_libexecdir}/speakerguardd/use-feedback-guard
install -Dm644 %{SOURCE2} %{buildroot}%{_unitdir}/speakersafetyd.service.d/50-j700-guard.conf

%post
%systemd_post speakerguardd.service
%preun
%systemd_preun speakerguardd.service
%postun
%systemd_postun_with_restart speakerguardd.service

%files
%license LICENSE
%{_bindir}/speakerguardd
%{_datadir}/speakerguardd/
%{_unitdir}/speakerguardd.service
%{_unitdir}/speakersafetyd.service.d/50-j700-guard.conf
%{_udevrulesdir}/95-speakerguardd.rules
%{_libexecdir}/speakerguardd/

%changelog
* Fri Oct 23 2026 Aurora Silicon <hey@djdev.me> - 0.1.0-3
- Install the J700 guard condition under libexec, so systemd runs it as an
  ordinary service program under SELinux instead of in its own init domain.
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
