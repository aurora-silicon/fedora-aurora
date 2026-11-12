%global commit 96f5aa45e6209cf94632d885a5b7c4c1bcc68209
Name: aurora-sep-luks
Version: 0.3.0
Release: 1%{?dist}
Summary: Unlock LUKS2 volumes with the Apple Secure Enclave
License: MIT
URL: https://github.com/aurora-silicon/aurora-sep-userspace
Source0: https://github.com/aurora-silicon/aurora-sep-userspace/archive/%{commit}/%{name}-%{commit}.tar.gz
ExclusiveArch: aarch64
BuildRequires: gcc make pkgconf-pkg-config cryptsetup-devel json-c-devel pam-devel
Requires: cryptsetup-libs >= 2.4
Requires: aurora-sep
# The initrd integration: a dracut module and its systemd units.
Recommends: dracut
BuildRequires: systemd-rpm-macros

%description
aurora-sep-cryptenroll enrolls this Mac's Secure Enclave as an unlock method
of a LUKS2 volume, like systemd-cryptenroll --tpm2-device=auto does with a
TPM. The keyslot secret is wrapped by a kernel trusted key that the apple_sep
driver seals. The libcryptsetup token plugin lets cryptsetup and
systemd-cryptsetup unlock enrolled volumes without a passphrase. The
passphrase keyslot is always kept. Nothing is enrolled by installing this
package.

The 90aurora-sep dracut module opens enrolled volumes in the initrd, the root
volume included, on kernels whose apple_sep driver has the key-store-only
attach phase. On older kernels it adds only the token plugin and those
volumes ask for their passphrase as before.

aurora-sep-fde unlocks a volume with a user's password, checked by the Secure
Enclave (the FileVault model): each user gets their own sealed keyslot, volume
owners (root and wheel members) add, remove and reset other users, a password
change re-wraps the user's key bag for every volume, and a recovery key opens
the volume and resets a password. pam_aurora_sep_fde keeps the disk password
equal to the login password when passwd or GNOME Settings changes it.

%prep
%autosetup -n aurora-sep-userspace-%{commit}

%build
%make_build -C luks CFLAGS="%{optflags}" LDFLAGS="%{build_ldflags}"

%check
# Exit 77 = the build root blocks the kernel keyring (seccomp); skipped.
make -C luks test/test-seal CFLAGS="%{optflags}"
./luks/test/test-seal || [ $? = 77 ]

%install
%make_install -C luks install install-dracut PREFIX=%{_prefix} \
	TOKENDIR=%{_libdir}/cryptsetup LIBEXECDIR=%{_libexecdir} UNITDIR=%{_unitdir} \
	PAMDIR=%{_libdir}/security SYSCONFDIR=%{_sysconfdir}

%files
%license LICENSES/MIT.txt
%doc docs/luks-sep.md docs/luks-sep-initrd.md docs/luks-sep-owners.md
%{_bindir}/aurora-sep-cryptenroll
%{_bindir}/aurora-sep-fde
%{_libexecdir}/aurora-sep-fde-passwd
%{_libdir}/security/pam_aurora_sep_fde.so
%dir %{_sysconfdir}/aurora-sep
%config(noreplace) %{_sysconfdir}/aurora-sep/fde.conf
%{_libdir}/cryptsetup/libcryptsetup-token-aurora-sep.so
%{_mandir}/man8/aurora-sep-cryptenroll.8*
%dir %{_prefix}/lib/aurora-sep
%{_prefix}/lib/aurora-sep/initrd/
%{_prefix}/lib/dracut/modules.d/90aurora-sep/
%{_libexecdir}/aurora-sep-initrd-check
%{_unitdir}/aurora-sep-initrd-check.service
%{_unitdir}/multi-user.target.wants/aurora-sep-initrd-check.service

%changelog
* Wed Nov 11 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.3.0-1
- aurora-sep-fde: password-sealed volumes with several users (FileVault
  model): volume owners add, remove and reset users; a password change
  re-wraps the user's key bag for every registered volume; recovery key
  as an offline keyslot or SEP-only (/etc/aurora-sep/fde.conf)
- pam_aurora_sep_fde and /usr/libexec/aurora-sep-fde-passwd: passwd and
  GNOME Settings also change the disk password
- Root volumes unlock in the initrd with the user's password through the SEP
  (keystore_only=2 kernels)
- boot-chain = audit (default) logs, per unlock, what require would refuse
  (chain state, first unverified link, volume); aurora-sep-fde boot-chain
  require switches a Mac once it boots verified and rebuilds the initramfs

* Sun Nov 08 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.2.0-1
- Open SEP-sealed volumes in the initrd, root included (90aurora-sep dracut
  module), on kernels with apple_sep's key-store-only phase
- The token plugin waits for the SEP key store without holding up the keyring

* Sun Nov 08 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.1.0-1
- SEP-sealed LUKS2 unlock: aurora-sep-cryptenroll and the aurora-sep token plugin
