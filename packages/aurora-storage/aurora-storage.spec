Name: aurora-storage
Version: 1
Release: 1%{?dist}
Summary: Driver-scoped Aurora storage defaults
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
Requires: systemd-udev
Source0: 60-aurora-apple-nvme.rules
Source1: README.md
Source2: LICENSE

%description
Default to the none I/O scheduler on Apple ANS namespace disks. Other storage
drivers and the kernel's request-size, read-ahead and polling defaults are
unchanged.

%prep

%build

%install
install -Dm644 %{SOURCE0} %{buildroot}%{_prefix}/lib/udev/rules.d/60-aurora-apple-nvme.rules
install -Dm644 %{SOURCE1} %{buildroot}%{_docdir}/%{name}/README.md
install -Dm644 %{SOURCE2} %{buildroot}%{_licensedir}/%{name}/LICENSE

%files
%{_prefix}/lib/udev/rules.d/60-aurora-apple-nvme.rules
%doc %{_docdir}/%{name}/README.md
%license %{_licensedir}/%{name}/LICENSE

%changelog
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-1
- Select none only for Apple ANS namespace disks; benchmark before merge.
