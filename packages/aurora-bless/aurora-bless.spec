%global commit 903a6304fd1b0ad40ef81956f4c9abfbfbac4d5a
Name: aurora-bless
Version: 0.4.4
Release: 2%{?dist}
Summary: Apple Silicon startup volume selector with Neo NVRAM support
License: MIT
URL: https://github.com/aurora-silicon/aurora-bless
Source0: aurora-bless-%{commit}.tar.gz
ExclusiveArch: aarch64
Provides: asahi-bless
Conflicts: asahi-bless
BuildRequires: rust cargo

%description
Apple Silicon startup volume selector with Neo NVRAM support. Built from the recorded Aurora source revision.

%prep
%autosetup -n aurora-bless-903a6304fd1b0ad40ef81956f4c9abfbfbac4d5a

%build
cargo build --locked --release -p asahi-bless

%check
cargo test --locked -p asahi-bless -p apple-nvram -p asahi-nvram

%install
install -Dm755 target/release/asahi-bless %{buildroot}%{_bindir}/aurora-bless
ln -s aurora-bless %{buildroot}%{_bindir}/asahi-bless

%files
%license LICENSE
%{_bindir}/aurora-bless
%{_bindir}/asahi-bless

%changelog
* Tue Nov 03 2026 Aurora Silicon <hey@djdev.me> - 0.4.4-2
- Pin aurora-bless 903a6304 (asahi-bless 0.4.4-neo.2, apple-nvram 0.4.0): Neo
  NVRAM writes work on GigaDevice flash and take the scoped write
  opt-in, so bless works on fresh installs.

* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
