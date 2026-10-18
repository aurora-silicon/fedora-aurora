%global commit 727b5895db67bd40aa66c41485c6a8f482d2a917
Name: aurora-bless
Version: 0.4.4
Release: 1%{?dist}
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
%autosetup -n aurora-bless-727b5895db67bd40aa66c41485c6a8f482d2a917

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
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
