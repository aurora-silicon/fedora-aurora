%global commit ffc201f33773541063f2f3d57c8a279cad5ede11
%global plugin_commit e5aa51a41f963e73b5a67914cae3c916a83739f1
# -s only: the helpers import their sibling modules from their own directory,
# which -P (safe path) would take off sys.path.
%global py3_shebang_flags s
# Aurora 2026-11-08: AirDrop over the Wi-Fi firmware's own AWDL (awdl0).
# kernel-aurora's brcmfmac already carries the AWDL interface support
# (aurora-silicon/linux#24, #183, #213), so this packages only the userspace:
# the omdrop-awdl helpers (create awdl0, open a discoverable window, send) and
# the receiver from omdrop-plugin. Everything is installed off.
Name:           omdrop-awdl
Version:        0.10.5
Release:        1%{?dist}.aurora1
Summary:        AirDrop over firmware-native AWDL on Apple Silicon Macs
License:        GPL-2.0-only AND MIT
URL:            https://github.com/netmojo-systems/omdrop-awdl
# Upstream main at 0.10.5 (ffc201f33773), pinned in sources.json.
Source0:        omdrop-awdl-%{commit}.tar.gz
# The receiver (bin/airdrop-serve.py and its modules), MIT; pinned in sources.json.
Source1:        omdrop-plugin-%{plugin_commit}.tar.gz
Source2:        README.aurora.md
# Aurora: accept Fedora's per-network cloned MAC once the station is associated
# (awdl-up otherwise refuses to derive awdl0's address on every Fedora install).
Patch0:         omdrop-awdl-0.10.5-stable-cloned-mac.patch
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  systemd-rpm-macros
Requires:       bash
Requires:       coreutils
Requires:       iproute
Requires:       iputils
Requires:       iw
Requires:       openssl
Requires:       polkit
Requires:       procps-ng
Requires:       python3
Requires:       python3-libarchive-c
Requires:       util-linux-core
%{?systemd_requires}
# Keeps awdl0 unmanaged and settles the Wi-Fi MAC before awdl0 is derived from it.
Recommends:     NetworkManager
# Thumbnails in the Ask an iPhone needs before it shows a prompt.
Recommends:     python3-pillow
# The Bluetooth advert that wakes a nearby Apple device's AirDrop listener.
Recommends:     bluez
Recommends:     python3-dbus
Recommends:     python3-gobject-base
# The optional cached Apple identity lives in the user keyring.
Suggests:       keyutils

%description
AWDL (Apple Wireless Direct Link) is the peer-to-peer Wi-Fi link AirDrop runs
over. The Broadcom Wi-Fi firmware on Apple Silicon Macs implements AWDL itself;
kernel-aurora's brcmfmac exposes it as an awdl0 interface. This package holds
the userspace from omdrop-awdl and omdrop-plugin: awdl-up creates and
configures awdl0, omdrop-discoverable opens a bounded discoverable window,
send-to-peer sends files and links to nearby Macs, iPhones and Linux Macs, and
the airdrop-receiver user service receives them.

Nothing runs until you ask: awdl0.service and awdl-warmup.service are
installed disabled, and the receiver is a user unit you start for a window.
See /usr/share/doc/omdrop-awdl/README.aurora.md.

%prep
%setup -q -n omdrop-awdl-%{commit}
%setup -q -T -D -a 1 -n omdrop-awdl-%{commit}
%patch -P0 -p1
cp -p %{SOURCE2} .
# Fedora keeps executables out of /usr/lib: install under %%{_libexecdir}
# (bin_t under SELinux). /usr/lib/omdrop-core, a separate package, keeps its path.
find userspace packaging -type f -exec \
	sed -i -E 's#/usr/lib/omdrop([/"<'"'"' ]|$)#%{_libexecdir}/omdrop\1#g' {} +
R=omdrop-plugin-%{plugin_commit}
cp -p $R/LICENSE LICENSE.omdrop-plugin
sed -i -e 's#@PLUGIN_DIR@#%{_datadir}/omdrop/receiver#g' \
	-e '0,/^ExecStartPre=/s##ExecStartPre=+/usr/bin/mkdir -p -m 0700 %%h/.omdrop\nExecStartPre=+/usr/bin/mkdir -p %%h/Downloads\n&#' \
	$R/share/airdrop-receiver.service
# The receiver writes its self-signed identity into ~/.omdrop; outside `omdrop
# setup` nothing creates that directory, and ProtectHome=read-only keeps the
# service from doing it, so create both writable paths before the sandbox.

%build
%py3_shebang_fix userspace omdrop-plugin-%{plugin_commit}/bin

%install
L=%{buildroot}%{_libexecdir}/omdrop
install -d $L/radio
for f in userspace/*; do
	[ -f "$f" ] || continue
	case $f in *.py|*.sh) m=644 ;; *) m=755 ;; esac
	install -pm $m "$f" $L/
done
# Run as scripts by the tools above.
chmod 755 $L/airdrop-send.py $L/awdl-*.py $L/ble-airdrop-adv.py $L/brcm_iovar.py $L/mkpsf.py
install -pm 755 userspace/radio/* $L/radio/
install -Dpm 644 packaging/awdl0.service %{buildroot}%{_unitdir}/awdl0.service
install -Dpm 644 packaging/awdl-warmup.service %{buildroot}%{_unitdir}/awdl-warmup.service
install -Dpm 755 packaging/omdrop-awdl-sleep %{buildroot}%{_systemd_util_dir}/system-sleep/omdrop-awdl
install -Dpm 644 packaging/org.omarchy.omdrop.policy %{buildroot}%{_datadir}/polkit-1/actions/org.omarchy.omdrop.policy
install -Dpm 644 packaging/99-awdl-unmanaged.conf %{buildroot}%{_prefix}/lib/NetworkManager/conf.d/99-awdl-unmanaged.conf
install -d %{buildroot}%{_presetdir}
printf 'disable awdl0.service\ndisable awdl-warmup.service\n' > %{buildroot}%{_presetdir}/90-omdrop-awdl.preset
R=omdrop-plugin-%{plugin_commit}
V=%{buildroot}%{_datadir}/omdrop/receiver
install -d $V/bin/apple-ca
for f in airdrop-serve.py contacts.py debugdump.py identity.py lifecycle.py safeplist.py; do
	install -pm 644 $R/bin/$f $V/bin/
done
chmod 755 $V/bin/airdrop-serve.py
install -pm 644 $R/bin/apple-ca/*.pem $V/bin/apple-ca/
# Apple's public root, which airdrop-serve.py loads at start (Contacts Only checks).
install -Dpm 644 $R/share/certs/apple_root_ca.pem $V/share/certs/apple_root_ca.pem
install -pm 644 $R/README.md $V/README.md
install -Dpm 644 $R/share/airdrop-receiver.service %{buildroot}%{_userunitdir}/airdrop-receiver.service
%py_byte_compile %{python3} $L
%py_byte_compile %{python3} $V/bin

%check
# Syntax of every installed script, by interpreter.
for f in %{buildroot}%{_libexecdir}/omdrop/* %{buildroot}%{_libexecdir}/omdrop/radio/* \
	 %{buildroot}%{_systemd_util_dir}/system-sleep/omdrop-awdl %{buildroot}%{_datadir}/omdrop/receiver/bin/*.py; do
	[ -f "$f" ] || continue
	case "$f" in *.sh) bash -n "$f"; continue ;; *.py) %{python3} -m py_compile "$f"; continue ;; esac
	case "$(head -n1 "$f")" in
	*bash*|*/sh) bash -n "$f" ;;
	*python*) %{python3} -m py_compile "$f" ;;
	esac
done
grep -q 'stable-ssid' %{buildroot}%{_libexecdir}/omdrop/awdl-up
if grep -rIl '/usr/lib/omdrop[/" ]' %{buildroot}%{_libexecdir} %{buildroot}%{_unitdir} \
	%{buildroot}%{_systemd_util_dir} %{buildroot}%{_datadir}/polkit-1; then exit 1; fi
test -s %{buildroot}%{_datadir}/omdrop/receiver/share/certs/apple_root_ca.pem
if grep -l '^#!.*python3 .*P' %{buildroot}%{_libexecdir}/omdrop/* %{buildroot}%{_datadir}/omdrop/receiver/bin/*.py 2>/dev/null; then exit 1; fi
if grep -q '@PLUGIN_DIR@' %{buildroot}%{_userunitdir}/airdrop-receiver.service; then exit 1; fi
grep -q '^ExecStartPre=+/usr/bin/mkdir -p -m 0700 %%h/.omdrop$' %{buildroot}%{_userunitdir}/airdrop-receiver.service
%{python3} -c 'import sys; sys.path.insert(0, "%{buildroot}%{_libexecdir}/omdrop"); import awdl_plist, awdl_identity'

%post
%systemd_post awdl0.service awdl-warmup.service
%systemd_user_post airdrop-receiver.service
%preun
%systemd_preun awdl0.service awdl-warmup.service
%systemd_user_preun airdrop-receiver.service
%postun
%systemd_postun awdl0.service awdl-warmup.service

%files
%license LICENSE LICENSE.omdrop-plugin
%doc README.md README.aurora.md
%{_libexecdir}/omdrop/
%{_unitdir}/awdl0.service
%{_unitdir}/awdl-warmup.service
%{_presetdir}/90-omdrop-awdl.preset
%{_systemd_util_dir}/system-sleep/omdrop-awdl
%{_datadir}/polkit-1/actions/org.omarchy.omdrop.policy
%{_prefix}/lib/NetworkManager/conf.d/99-awdl-unmanaged.conf
%{_datadir}/omdrop/
%{_userunitdir}/airdrop-receiver.service

%changelog
* Sun Nov 08 2026 Ryan Murray <81541646+RyanTheTide@users.noreply.github.com> - 0.10.5-1.aurora1
- Package omdrop-awdl 0.10.5 (helpers only; kernel-aurora's brcmfmac has AWDL)
  and the omdrop-plugin receiver; helpers in /usr/libexec/omdrop; all units
  installed disabled; accept Fedora's stable-ssid cloned MAC once associated;
  the receiver unit creates ~/.omdrop and ~/Downloads before its sandbox;
  python shebangs keep the script directory on sys.path (-s, not -sP).
