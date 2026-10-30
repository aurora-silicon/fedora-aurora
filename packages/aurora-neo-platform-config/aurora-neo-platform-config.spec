%global commit 8f18039e37ccdec03049d04844d59de2909f680c
Name: aurora-neo-platform-config
Version: 0.1.0
Release: 2%{?dist}
Summary: MacBook Neo network and trackpad configuration
License: MIT
URL: https://github.com/aurora-silicon/aurora-neo-platform-config
Source0: aurora-neo-platform-config-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: make

%description
MacBook Neo network and trackpad configuration. Built from the recorded Aurora source revision.

%prep
%autosetup -n aurora-neo-platform-config-8f18039e37ccdec03049d04844d59de2909f680c

%build

%install
%make_install PREFIX=%{_prefix}

%check
sh tests/run.sh

%files
%license LICENSE
%doc README.md
%{_prefix}/lib/NetworkManager/conf.d/80-aurora-neo-mt7932.conf
%{_datadir}/libinput/60-aurora-neo-j700.quirks

%changelog
* Thu Oct 30 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-2
- Track main at 8f18039: the J700 trackpad libinput quirk. The kernel
  reports palms as MT_TOOL_PALM, so size-based palm detection is turned off
  for this trackpad and flat thumbs are no longer rejected.
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
