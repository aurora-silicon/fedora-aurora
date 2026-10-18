%global commit 8e6f96f06d0e51c2a1dc513cf2fdf57ab32a2a64
Name: bankstown
Version: 1.1.0
Release: 1%{?dist}
Summary: LV2 bass enhancement plugin used by Apple Silicon audio profiles
License: MIT
URL: https://github.com/chadmed/bankstown
Source0: bankstown-%{commit}.tar.gz
ExclusiveArch: aarch64
BuildRequires: rust cargo make

%description
Bankstown LV2 bass enhancement used by the Aurora audio graphs.

%prep
%autosetup -n bankstown-%{commit}
%build
cargo build --locked --release
%check
cargo test --locked
%install
make install DESTDIR=%{buildroot} LIBDIR=%{_libdir}
%files
%license LICENSE
%{_libdir}/lv2/bankstown.lv2/
%changelog
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1.1.0-1
- Initial Fedora Aurora package.
