%global commit 834fe2dda273540b184b57ed16985b9d7effd244
Name: aurora-neo-platform-config
Version: 0.1.0
Release: 1%{?dist}
Summary: MacBook Neo network configuration
License: MIT
URL: https://github.com/aurora-silicon/aurora-neo-platform-config
Source0: aurora-neo-platform-config-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: make

%description
MacBook Neo network configuration. Built from the recorded Aurora source revision.

%prep
%autosetup -n aurora-neo-platform-config-834fe2dda273540b184b57ed16985b9d7effd244

%build

%install
%make_install PREFIX=%{_prefix}

%check
sh tests/run.sh

%files
%license LICENSE
%doc README.md
%{_prefix}/lib/NetworkManager/conf.d/80-aurora-neo-mt7932.conf

%changelog
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
