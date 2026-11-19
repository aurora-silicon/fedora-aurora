Name: plymouth-theme-aurora
Version: 1
Release: 9%{?dist}
Summary: Aurora boot splash: the bootloader's logo, kept in place, with the distribution's branding
# The spinner, password entry and watermark images come from the distribution's
# spinner theme (ImageDir); this package adds the script and aura's logos.
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
# Renderer removal must detach the script plugin before its keyboard is freed.
# Both Fedora carries provide this after fixing the core and script plugin.
Requires: plymouth(script-keyboard-lifetime) >= 1
Requires: plymouth-plugin-script
Requires: plymouth-plugin-label
Requires: plymouth-theme-spinner
Requires: font(cantarell)
Requires(post): plymouth-scripts
Requires(postun): plymouth-scripts

Source100: aurora.plymouth
Source101: aurora.script
# Byte-identical to aura's data/aurora_128.png and data/aurora_256.png, the logos
# aura draws on other displays and on Retina panels.
Source102: aurora-logo-128.png
Source103: aurora-logo-256.png
Source104: aurora-plymouth
Source105: aurora-plymouth.conf
Source106: module-setup.sh
Source107: prepare.sh
Source108: test_geometry.py
BuildRequires: python3
BuildRequires: systemd-rpm-macros
Requires: coreutils
Requires: dracut
Requires(posttrans): grubby

%description
The Aurora boot splash. aura (the bootloader) draws the Aurora logo centred on a
black screen and U-Boot leaves it there; this theme draws the same image, at the
same size and place on every panel, so the logo stays still from power-on until
the login screen. The spinner sits below it and the distribution's own branding
(the spinner theme's watermark, Fedora's on Fedora) at the bottom. Disk
passwords are asked on the same screen. Press Esc to see the boot messages.

%prep

%build

%install
d=%{buildroot}%{_datadir}/plymouth/themes/aurora
install -Dm644 %{SOURCE100} $d/aurora.plymouth
install -Dm644 %{SOURCE101} $d/aurora.script
install -Dm644 %{SOURCE102} $d/aurora-logo-128.png
install -Dm644 %{SOURCE103} $d/aurora-logo-256.png
install -Dm755 %{SOURCE104} %{buildroot}%{_libexecdir}/aurora-plymouth
install -Dm644 %{SOURCE105} %{buildroot}%{_unitdir}/plymouth-start.service.d/aurora-plymouth.conf
install -Dm755 %{SOURCE106} %{buildroot}%{_prefix}/lib/dracut/modules.d/96aurora-plymouth/module-setup.sh
install -Dm755 %{SOURCE107} %{buildroot}%{_prefix}/lib/dracut/modules.d/96aurora-plymouth/prepare.sh

%check
python3 %{SOURCE108} %{_sourcedir}

%post
conf=%{_sysconfdir}/plymouth/plymouthd.conf
# Make Aurora the splash while the current one is a stock Fedora default (none
# chosen, or bgrt, spinner or charge, which Fedora's own scriptlets set), on new
# images and on installs updated from before this theme. Any other theme is the
# owner's choice and stays.
case "$(%{_bindir}/plymouth-set-default-theme 2>/dev/null)" in
  ''|bgrt|spinner|charge)
    %{_bindir}/plymouth-set-default-theme aurora || : ;;
esac
# The theme draws in device pixels, so the logo matches aura's to the pixel;
# Plymouth's own 2x scale on Retina panels would double it. An owner's own
# DeviceScale wins.
if [ "$(%{_bindir}/plymouth-set-default-theme 2>/dev/null)" = aurora ] &&
   ! grep -qs '^[[:space:]]*DeviceScale[[:space:]]*=' $conf; then
  sed -i '/^[[:space:]]*\[Daemon\][[:space:]]*$/a # Set by plymouth-theme-aurora, which draws in device pixels\nDeviceScale=1' $conf || :
fi
# The splash runs from the initramfs, which holds its own copy of the theme
# and of plymouthd.conf: rebuild it whenever Aurora is the splash, on an
# update too, or the boot keeps showing the previous theme files.
if [ "$(%{_bindir}/plymouth-set-default-theme 2>/dev/null)" = aurora ]; then
  mkdir -p %{_localstatedir}/lib/rpm-state
  touch %{_localstatedir}/lib/rpm-state/plymouth-theme-aurora-initrd
fi

%posttrans
# aura names a debug UART as the device tree's stdout-path only on a debug
# boot (aura-debug, aura-console or chosen.aura,serial-console=1), so a normal
# boot has no serial console and Plymouth keeps its graphical view without
# plymouth.ignore-serial-consoles. Earlier releases added that argument to
# every boot entry; take it out once, so a later owner's choice stays.
removed=%{_localstatedir}/lib/aurora/plymouth-serial-arg-removed
cmdline=%{_sysconfdir}/kernel/cmdline
carries() { grep -qE '(^|[[:space:]"])plymouth\.ignore-serial-consoles([[:space:]"]|$)'; }
if [ ! -e $removed ]; then
  if { [ -f $cmdline ] && carries < $cmdline; } ||
     %{_sbindir}/grubby --info=ALL 2>/dev/null | grep -E '^args=' | carries; then
    %{_sbindir}/grubby --update-kernel=ALL --remove-args=plymouth.ignore-serial-consoles || :
  fi
  mkdir -p "$(dirname $removed)" && touch $removed || :
fi
# Rebuild the initramfs once per transaction when asked above, on a running
# system; an image build makes its own initramfs afterwards.
flag=%{_localstatedir}/lib/rpm-state/plymouth-theme-aurora-initrd
if [ -e $flag ]; then
  rm -f $flag
  if [ -d /run/systemd/system ]; then
    dracut -f --regenerate-all >/dev/null 2>&1 || :
  fi
fi

%postun
if [ $1 -eq 0 ]; then
  conf=%{_sysconfdir}/plymouth/plymouthd.conf
  sed -i '/^# Set by plymouth-theme-aurora, which draws in device pixels$/{N;/\nDeviceScale=1$/d}' $conf 2>/dev/null || :
  if [ "$(%{_bindir}/plymouth-set-default-theme 2>/dev/null)" = aurora ]; then
    %{_bindir}/plymouth-set-default-theme --reset || :
  fi
fi

%files
%dir %{_datadir}/plymouth/themes/aurora
%{_datadir}/plymouth/themes/aurora/aurora.plymouth
%{_datadir}/plymouth/themes/aurora/aurora.script
%{_datadir}/plymouth/themes/aurora/aurora-logo-128.png
%{_datadir}/plymouth/themes/aurora/aurora-logo-256.png

%{_libexecdir}/aurora-plymouth
%{_unitdir}/plymouth-start.service.d/aurora-plymouth.conf
%{_prefix}/lib/dracut/modules.d/96aurora-plymouth

%changelog
* Thu Nov 19 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-9
- Stop adding plymouth.ignore-serial-consoles and remove it once from
  installed boot entries: aura keeps a debug UART out of stdout-path on
  normal boots, so there is no serial console for Plymouth to give way to.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-8
- Add plymouth.ignore-serial-consoles to boot entries that lack it even when
  /etc/kernel/cmdline already has it.

* Tue Nov 10 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-7
- Rebuild the initramfs on updates as well: it holds its own copy of the
  theme and plymouthd.conf, so an updated system kept booting the previous
  splash (an older theme drew the logo twice aura's size on Retina panels).

* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-6
- Add plymouth.ignore-serial-consoles to installed systems that boot with
  rhgb: the Neo's DockChannel console made Plymouth show its text view, so
  the splash and the graphical disk passphrase entry never appeared.

* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-5
- Switch to the Aurora splash on update when the current theme is a stock
  default (bgrt, spinner or charge) and rebuild the initramfs; an owner's
  other theme stays.

* Mon Nov 02 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-4
- Keep the logo at aura's physical position when notch rows are hidden.
- Read the live device tree before Plymouth starts on each boot.
- Share the crash fix that removes caps-lock polling from the theme.

* Mon Nov 02 2026 Ryan Murray <ryan@aurorasilicon.org> - 1-3
- Require Plymouth's renderer keyboard lifetime fix for safe splash hide.
- Avoid keyboard access in the theme.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 1-2
- Draw the logo at aura's size and place on every panel: 256 px on Retina
  panels and 128 px elsewhere, in device pixels. Plymouth's 2x scale had
  doubled it on the 14 and 16 inch MacBook Pros.
- Show the distribution's own branding at the bottom, from the spinner
  theme's watermark, as the stock splash does.
- Use the script plugin; the spinner and password entry still come from the
  spinner theme.

* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 1-1
- Initial package: the aura logo, centred, with the spinner below it.
