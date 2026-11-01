Name: plymouth-theme-aurora
Version: 1
Release: 1%{?dist}
Summary: Aurora boot splash: the bootloader's logo with a spinner
# The spinner, dialog and keyboard images come from Fedora's plymouth-theme-spinner
# (symlinked, not copied); this package adds the theme file and the Aurora logo.
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
BuildRequires: plymouth-theme-spinner
Requires: plymouth-plugin-two-step
Requires: plymouth-plugin-label
Requires: plymouth-theme-spinner
Requires(post): plymouth-scripts
Requires(postun): plymouth-scripts

Source100: aurora.plymouth
# Byte-identical to aura's data/aurora_256.png, the logo Stage 1 draws centred on Retina panels.
Source101: aurora-logo-256.png

%description
The Aurora boot splash. aura (the bootloader) draws the Aurora logo centred on a
black screen; this theme draws the same 256 px image at the same place, with
Fedora's spinner below it, so the logo stays still from power-on until the login
screen. Disk passwords are asked on the same screen. Press Esc to see the boot
messages.

%prep

%build

%install
d=%{buildroot}%{_datadir}/plymouth/themes/aurora
install -Dm644 %{SOURCE100} $d/aurora.plymouth
install -Dm644 %{SOURCE101} $d/watermark.png
# two-step reads every image from ImageDir; reuse the spinner theme's animation
# and dialog images. dracut's plymouth module installs the link targets too.
for f in %{_datadir}/plymouth/themes/spinner/*.png; do
  case ${f##*/} in watermark.png) continue;; esac
  ln -s ../spinner/${f##*/} $d/${f##*/}
done

%post
# Make Aurora the splash unless the owner already chose a theme.
if ! grep -qs '^[[:space:]]*Theme[[:space:]]*=' %{_sysconfdir}/plymouth/plymouthd.conf; then
  %{_bindir}/plymouth-set-default-theme aurora || :
fi

%postun
if [ $1 -eq 0 ] && [ "$(%{_bindir}/plymouth-set-default-theme 2>/dev/null)" = aurora ]; then
  %{_bindir}/plymouth-set-default-theme --reset || :
fi

%files
%dir %{_datadir}/plymouth/themes/aurora
%{_datadir}/plymouth/themes/aurora/aurora.plymouth
%{_datadir}/plymouth/themes/aurora/*.png

%changelog
* Sun Nov 01 2026 Aurora Silicon <hey@djdev.me> - 1-1
- Initial package: the aura logo, centred, with the spinner below it.
