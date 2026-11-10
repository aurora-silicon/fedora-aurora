%global commit 63a51a73377dafc1aafdbe86d398d505fa939ff7
Name: aurora-sep-luks
Version: 0.1.0
Release: 1%{?dist}
Summary: Unlock LUKS2 volumes with the Apple Secure Enclave
License: MIT
URL: https://github.com/aurora-silicon/aurora-sep-userspace
Source0: https://github.com/aurora-silicon/aurora-sep-userspace/archive/%{commit}/%{name}-%{commit}.tar.gz
ExclusiveArch: aarch64
BuildRequires: gcc make pkgconf-pkg-config cryptsetup-devel json-c-devel
Requires: cryptsetup-libs >= 2.4
Requires: aurora-sep

%description
aurora-sep-cryptenroll enrolls this Mac's Secure Enclave as an unlock method
of a LUKS2 volume, like systemd-cryptenroll --tpm2-device=auto does with a
TPM. The keyslot secret is wrapped by a kernel trusted key that the apple_sep
driver seals. The libcryptsetup token plugin lets cryptsetup and
systemd-cryptsetup unlock enrolled volumes without a passphrase. The
passphrase keyslot is always kept. Nothing is enrolled by installing this
package.

%prep
%autosetup -n aurora-sep-userspace-%{commit}

%build
%make_build -C luks CFLAGS="%{optflags}" LDFLAGS="%{build_ldflags}"

%check
# Exit 77 = the build root blocks the kernel keyring (seccomp); skipped.
make -C luks test/test-seal CFLAGS="%{optflags}"
./luks/test/test-seal || [ $? = 77 ]

%install
%make_install -C luks PREFIX=%{_prefix} TOKENDIR=%{_libdir}/cryptsetup

%files
%license LICENSES/MIT.txt
%doc docs/luks-sep.md
%{_bindir}/aurora-sep-cryptenroll
%{_libdir}/cryptsetup/libcryptsetup-token-aurora-sep.so
%{_mandir}/man8/aurora-sep-cryptenroll.8*

%changelog
* Sun Nov 08 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1.0-1
- SEP-sealed LUKS2 unlock: aurora-sep-cryptenroll and the aurora-sep token plugin
