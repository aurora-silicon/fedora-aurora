Name: plymouth-theme-aurora
Version: 1
Release: 2%{?dist}
Summary: Aurora boot splash: the bootloader's logo, kept in place, with the distribution's branding
# The spinner, password entry and watermark images come from the distribution's
# spinner theme (ImageDir); this package adds the script and aura's logos.
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
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

%post
conf=%{_sysconfdir}/plymouth/plymouthd.conf
# Make Aurora the splash unless the owner already chose a theme.
if ! grep -qs '^[[:space:]]*Theme[[:space:]]*=' $conf; then
  %{_bindir}/plymouth-set-default-theme aurora || :
fi
# The theme draws in device pixels, so the logo matches aura's to the pixel;
# Plymouth's own 2x scale on Retina panels would double it. An owner's own
# DeviceScale wins.
if [ "$(%{_bindir}/plymouth-set-default-theme 2>/dev/null)" = aurora ] &&
   ! grep -qs '^[[:space:]]*DeviceScale[[:space:]]*=' $conf; then
  sed -i '/^[[:space:]]*\[Daemon\][[:space:]]*$/a # Set by plymouth-theme-aurora, which draws in device pixels\nDeviceScale=1' $conf || :
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

%changelog
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
