Summary: Graphical Boot Animation and Logger
Name: plymouth
Version: 26.134.222
Release: 6%{?dist}.aurora5
License: GPL-2.0-or-later
URL: http://www.freedesktop.org/wiki/Software/Plymouth

Source0: https://gitlab.freedesktop.org/plymouth/plymouth/-/archive/%{version}/%{name}-%{version}.tar.bz2
Source1: charge.plymouth

# Fix race in fb_device_has_drm_device () causing frame-buffer plugin to
# sometimes load while drm plugin is already handling the display
Patch: 0001-ply-device-manager-Fix-race-in-fb_device_has_drm_dev.patch

# For https://bugzilla.redhat.com/show_bug.cgi?id=2481687
# https://gitlab.freedesktop.org/plymouth/plymouth/-/commit/cea90be39d263e388003a07d125b469c0803d55c
Patch: 0001-ply-device-manager-fix-default-XKB-keymap-fallback-o.patch

Patch: 0001-ply-terminal-Keep-terminal-input-nonblocking.patch
# Show the splash as soon as udevd runs instead of after the whole coldplug
# has been queued; plymouthd follows udev add events and needs neither.
Patch: 0001-systemd-units-Start-plymouthd-without-waiting-for-coldplug.patch
Source2: test-terminal-input.c
Source3: test-keyboard-lifetime.c
Source4: test-script-keyboard.c
Source5: check-keyboard-lifetime.sh
Source6: test-drm-sdr.c
# The DRM master can hand off before the HDR compositor closes its file.
Patch: 0002-drm-Reset-inherited-HDR-connector-state-before-SDR.patch
Patch: 0001-Fix-splash-keyboard-lifetime.patch
BuildRequires: xorg-x11-server-Xvfb
BuildRequires: font(cantarell)

BuildRequires: meson
BuildRequires: system-logos
BuildRequires: gcc libtool git
BuildRequires: pkgconfig(libdrm)
BuildRequires: pkgconfig(libevdev)
BuildRequires: pkgconfig(libudev)
BuildRequires: pkgconfig(xkeyboard-config)
BuildRequires: kernel-headers
BuildRequires: libpng-devel
BuildRequires: libxslt, docbook-style-xsl
BuildRequires: pkgconfig(gtk+-3.0)
BuildRequires: pango-devel >= 1.21.0
BuildRequires: cairo-devel
BuildRequires: gettext-devel
# for /usr/bin/systemd-tty-ask-password-agent
BuildRequires: systemd
# for _unitdir macro
BuildRequires: systemd-rpm-macros

Requires: %{name}-core-libs = %{version}-%{release}
Requires: %{name}-scripts = %{version}-%{release}
# For keyboard layouts
Requires: xkeyboard-config
Suggests: logrotate
# Aurora installs boot to aura's splash; an update brings it to installs made
# before the theme existed. Minimal images carry no Plymouth and so no theme.
Recommends: plymouth-theme-aurora

%description
Plymouth provides an attractive graphical boot animation in
place of the text messages that normally get shown.  Text
messages are instead redirected to a log file for viewing
after boot.


%package system-theme
Summary: Plymouth default theme
Requires: plymouth(system-theme) = %{version}-%{release}

%description system-theme
This meta-package tracks the current distribution default theme.


%package core-libs
Summary: Plymouth core libraries

%description core-libs
This package contains the core libraries used by Plymouth.


%package graphics-libs
Summary: Plymouth graphics libraries
Requires: %{name}-core-libs = %{version}-%{release}
Requires: system-logos

%description graphics-libs
This package contains the libraries used by graphical Plymouth splashes.


%package devel
Summary: Libraries and headers for writing Plymouth splash plugins
Requires: %{name} = %{version}-%{release}
Requires: pkgconfig

%description devel
This package contains the libraries and headers needed to develop
3rd party splash plugins for Plymouth.


%package scripts
Summary: Plymouth related scripts
Requires: findutils, coreutils, gzip, cpio, dracut
Requires: xkeyboard-config
Requires: %{name} = %{version}-%{release}

%description scripts
This package contains scripts that help integrate Plymouth with
the system.


%package plugin-label
Summary: Plymouth label plugin
Requires: %{name} = %{version}-%{release}
Requires: %{name}-graphics-libs = %{version}-%{release}

%description plugin-label
This package contains the label control plugin for Plymouth.
It provides the ability to render text on graphical boot splashes.


%package plugin-script
Summary: Plymouth "script" plugin
Requires: %{name} = %{version}-%{release}
Requires: %{name}-graphics-libs = %{version}-%{release}

Provides: plymouth(script-keyboard-lifetime) = 1

%description plugin-script
This package contains the "script" boot splash plugin for
Plymouth. It features an extensible boot splash language that
allows writing new plugins as scripts, simplifying the process
of designing custom boot splash themes.


%package plugin-fade-throbber
Summary: Plymouth "Fade-Throbber" plugin
Requires: %{name} = %{version}-%{release}
Requires: %{name}-graphics-libs = %{version}-%{release}

%description plugin-fade-throbber
This package contains the "Fade-In" boot splash plugin for
Plymouth. It features a centered image that fades in and out
while other images pulsate around during system boot up.


%package plugin-space-flares
Summary: Plymouth "space-flares" plugin
Requires: %{name} = %{version}-%{release}
Requires: %{name}-graphics-libs = %{version}-%{release}
Requires: plymouth-plugin-label = %{version}-%{release}

%description plugin-space-flares
This package contains the "space-flares" boot splash plugin for
Plymouth. It features a corner image with animated flares.


%package plugin-two-step
Summary: Plymouth "two-step" plugin
Requires: %{name} = %{version}-%{release}
Requires: %{name}-graphics-libs = %{version}-%{release}
Requires: plymouth-plugin-label = %{version}-%{release}
# Spinifinity like themes should now use two-step instead of throbgress
# No provides, the throbgress plugin has been removed upstream
Obsoletes: %{name}-plugin-throbgress < %{version}-%{release}

%description plugin-two-step
This package contains the "two-step" boot splash plugin for
Plymouth. It features a two phased boot process that starts with
a progressing animation synced to boot time and finishes with a
short, fast one-shot animation.

# Don't build charge theme in ELN/RHEL as it's Fedora specific
%if ! 0%{?rhel}
%package theme-charge
Summary: Plymouth "Charge" plugin
Requires: %{name}-plugin-two-step = %{version}-%{release}
Requires: fedora-logos-classic
Requires(post): plymouth-scripts

%description theme-charge
This package contains the "charge" boot splash theme for
Plymouth. It features the shadowy hull of a Fedora logo charge up and
and finally burst into full form.
%endif

%package theme-fade-in
Summary: Plymouth "Fade-In" theme
Requires: %{name}-plugin-fade-throbber = %{version}-%{release}
Requires(post): plymouth-scripts

%description theme-fade-in
This package contains the "Fade-In" boot splash theme for
Plymouth. It features a centered logo that fades in and out
while stars twinkle around the logo during system boot up.


%package theme-script
Summary: Plymouth "Script" plugin
Requires: %{name}-plugin-script = %{version}-%{release}
Requires(post): plymouth-scripts

%description theme-script
This package contains the "script" boot splash theme for
Plymouth. It it is a simple example theme the uses the "script"
plugin.


%package theme-solar
Summary: Plymouth "Solar" theme
Requires: %{name}-plugin-space-flares = %{version}-%{release}
Requires(post): plymouth-scripts

%description theme-solar
This package contains the "Solar" boot splash theme for
Plymouth. It features a blue flamed sun with animated solar flares.


%package theme-spinfinity
Summary: Plymouth "Spinfinity" theme
Requires: %{name}-plugin-two-step = %{version}-%{release}
Requires(post): plymouth-scripts

%description theme-spinfinity
This package contains the "Spinfinity" boot splash theme for
Plymouth. It features a centered logo and animated spinner that
spins in the shape of an infinity sign.


%package theme-spinner
Summary: Plymouth "Spinner" theme
Requires: %{name}-plugin-two-step = %{version}-%{release}
%if 0%{?rhel} > 9
Requires: redhat-mono-vf-fonts
Requires: redhat-text-vf-fonts
%else
Requires: font(cantarell) font(cantarelllight)
%endif
Requires(post): plymouth-scripts
Provides: plymouth(system-theme) = %{version}-%{release}

%description theme-spinner
This package contains the "spinner" boot splash theme for
Plymouth. It features a small spinner on a dark background.


%prep
%autosetup -p1
# Change the default theme
sed -i -e 's/spinner/bgrt/g' src/plymouthd.defaults
# Use simpledrm /dev/dri/card# by default, except when LUKS disk encrpytion is used
echo UseSimpledrmNoLuks=1 >> src/plymouthd.defaults

%if 0%{?rhel} > 9
find -type f -exec sed -i -e 's/Cantarell/Red Hat Text/g' {} \;
%endif

%build
%meson -Dtracing=true  \
       -Dlogo=%{_datadir}/pixmaps/system-logo-white.png \
       -Dbackground-start-color-stop=0x0073B3           \
       -Dbackground-end-color-stop=0x00457E             \
       -Dbackground-color=0x3391cd
%meson_build

%check
bash %{SOURCE5} "$PWD" "$PWD/%{_vpath_builddir}" "%{_sourcedir}"
# These releases predate the upstream Meson test harness.
# Compile the same PTY regression against the libraries just built.
%{__cc} -D_GNU_SOURCE -Wall -Wextra -Werror \
    -I. -Isrc/libply -Isrc/libply-splash-core \
    %{SOURCE2} -o test-terminal-input \
    -L%{_vpath_builddir}/src/libply-splash-core -L%{_vpath_builddir}/src/libply \
    -Wl,-rpath,$PWD/%{_vpath_builddir}/src/libply-splash-core \
    -Wl,-rpath,$PWD/%{_vpath_builddir}/src/libply \
    -lply-splash-core -lply
timeout 15s ./test-terminal-input
echo "Plymouth terminal-input PTY regression passed"
%{__cc} -D_GNU_SOURCE -Wall \
    -I. -Isrc/libply -Isrc/libply-splash-core \
    $(pkg-config --cflags libdrm libevdev) \
    %{SOURCE6} -o test-drm-sdr \
    -L%{_vpath_builddir}/src/libply-splash-core -L%{_vpath_builddir}/src/libply \
    -Wl,-rpath,$PWD/%{_vpath_builddir}/src/libply-splash-core \
    -Wl,-rpath,$PWD/%{_vpath_builddir}/src/libply \
    -lply-splash-core -lply $(pkg-config --libs libdrm libevdev) -lm
timeout 15s ./test-drm-sdr


%install
%meson_install

%find_lang %{name}
find $RPM_BUILD_ROOT -name '*.la' -delete

mkdir -p $RPM_BUILD_ROOT%{_localstatedir}/lib/plymouth

%if ! 0%{?rhel}
# Add charge, our old default
mkdir -p $RPM_BUILD_ROOT%{_datadir}/plymouth/themes/charge
cp %{SOURCE1} $RPM_BUILD_ROOT%{_datadir}/plymouth/themes/charge
cp $RPM_BUILD_ROOT%{_datadir}/plymouth/themes/glow/{box,bullet,entry,lock}.png $RPM_BUILD_ROOT%{_datadir}/plymouth/themes/charge
%endif

# Drop glow, it's not very Fedora-y
rm -rf $RPM_BUILD_ROOT%{_datadir}/plymouth/themes/glow


%ldconfig_scriptlets core-libs

%ldconfig_scriptlets graphics-libs

%if ! 0%{?rhel}
%postun theme-charge
export PLYMOUTH_PLUGIN_PATH=%{_libdir}/plymouth/
if [ $1 -eq 0 ]; then
    if [ "$(%{_sbindir}/plymouth-set-default-theme)" == "charge" ]; then
        %{_sbindir}/plymouth-set-default-theme --reset
    fi
fi
%endif

%postun theme-fade-in
export PLYMOUTH_PLUGIN_PATH=%{_libdir}/plymouth/
if [ $1 -eq 0 ]; then
    if [ "$(%{_sbindir}/plymouth-set-default-theme)" == "fade-in" ]; then
        %{_sbindir}/plymouth-set-default-theme --reset
    fi
fi

%postun theme-solar
export PLYMOUTH_PLUGIN_PATH=%{_libdir}/plymouth/
if [ $1 -eq 0 ]; then
    if [ "$(%{_sbindir}/plymouth-set-default-theme)" == "solar" ]; then
        %{_sbindir}/plymouth-set-default-theme --reset
    fi
fi

%postun theme-spinfinity
export PLYMOUTH_PLUGIN_PATH=%{_libdir}/plymouth/
if [ $1 -eq 0 ]; then
    if [ "$(%{_sbindir}/plymouth-set-default-theme)" == "spinfinity" ]; then
        %{_sbindir}/plymouth-set-default-theme --reset
    fi
fi

%post theme-spinner
export PLYMOUTH_PLUGIN_PATH=%{_libdir}/plymouth/
# On upgrades replace charge with the new bgrt default
if [ $1 -eq 2 ]; then
    if [ "$(%{_sbindir}/plymouth-set-default-theme)" == "charge" ]; then
        %{_sbindir}/plymouth-set-default-theme bgrt
    fi
fi

%postun theme-spinner
export PLYMOUTH_PLUGIN_PATH=%{_libdir}/plymouth/
if [ $1 -eq 0 ]; then
    if [ "$(%{_sbindir}/plymouth-set-default-theme)" == "bgrt" -o \
         "$(%{_sbindir}/plymouth-set-default-theme)" == "spinner" ]; then
        %{_sbindir}/plymouth-set-default-theme --reset
    fi
fi


%files -f %{name}.lang
%license COPYING
%doc AUTHORS README.md
%dir %{_datadir}/plymouth
%dir %{_datadir}/plymouth/themes
%dir %{_datadir}/plymouth/themes/details
%dir %{_datadir}/plymouth/themes/text
%dir %{_datadir}/plymouth/themes/tribar
%dir %{_libexecdir}/plymouth
%dir %{_localstatedir}/lib/plymouth
%dir %{_libdir}/plymouth/renderers
%dir %{_sysconfdir}/plymouth
%config(noreplace) %{_sysconfdir}/plymouth/plymouthd.conf
%config(noreplace) %{_sysconfdir}/logrotate.d/bootlog
%{_sbindir}/plymouthd
%{_libexecdir}/plymouth/plymouthd-fd-escrow
%{_bindir}/plymouth
%{_libdir}/plymouth/details.so
%{_libdir}/plymouth/text.so
%{_libdir}/plymouth/tribar.so
%{_datadir}/plymouth/themes/details/details.plymouth
%{_datadir}/plymouth/themes/text/text.plymouth
%{_datadir}/plymouth/themes/tribar/tribar.plymouth
%{_datadir}/plymouth/plymouthd.defaults
%{_localstatedir}/spool/plymouth
%{_mandir}/man?/*
%ghost %attr(0644,root,root) %{_localstatedir}/lib/plymouth/boot-duration
%{_unitdir}/

%files devel
%{_libdir}/libply.so
%{_libdir}/libply-splash-core.so
%{_libdir}/libply-boot-client.so
%{_libdir}/libply-splash-graphics.so
%{_libdir}/pkgconfig/ply-splash-core.pc
%{_libdir}/pkgconfig/ply-splash-graphics.pc
%{_libdir}/pkgconfig/ply-boot-client.pc
%{_libdir}/plymouth/renderers/x11*
%{_includedir}/plymouth-1

%files core-libs
%{_libdir}/libply.so.*
%{_libdir}/libply-splash-core.so.*
%{_libdir}/libply-boot-client.so.*
%dir %{_libdir}/plymouth

%files graphics-libs
%{_libdir}/libply-splash-graphics.so.*
%{_libdir}/plymouth/renderers/drm*
%{_libdir}/plymouth/renderers/frame-buffer*

%files scripts
%{_sbindir}/plymouth-set-default-theme
%{_libexecdir}/plymouth/plymouth-update-initrd
%{_libexecdir}/plymouth/plymouth-generate-initrd
%{_libexecdir}/plymouth/plymouth-populate-initrd

%files plugin-label
%{_libdir}/plymouth/label-freetype.so
%{_libdir}/plymouth/label-pango.so

%files plugin-script
%{_libdir}/plymouth/script.so

%files plugin-fade-throbber
%{_libdir}/plymouth/fade-throbber.so

%files plugin-space-flares
%{_libdir}/plymouth/space-flares.so

%files plugin-two-step
%{_libdir}/plymouth/two-step.so

%if ! 0%{?rhel}
%files theme-charge
%{_datadir}/plymouth/themes/charge
%endif

%files theme-fade-in
%{_datadir}/plymouth/themes/fade-in

%files theme-script
%{_datadir}/plymouth/themes/script

%files theme-solar
%{_datadir}/plymouth/themes/solar

%files theme-spinfinity
%{_datadir}/plymouth/themes/spinfinity

%files theme-spinner
# bgrt is a variant of spinner with different settings in its .plymouth file
%{_datadir}/plymouth/themes/bgrt
%{_datadir}/plymouth/themes/spinner

%files system-theme

%changelog
* Wed Nov 04 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.134.222-6.aurora5
- Clear inherited HDR metadata and colorspace before presenting the SDR splash
- Test DRM handoffs, cloned outputs and failed commits without hardware

* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.134.222-6.aurora4
- Build 26.134.222 on Fedora 44 too. The 24.004.60 carry came back with
  the theme merge and would have downgraded the published
  26.134.222-6.aurora2, which also left the theme without the
  keyboard-lifetime Provides it needs on Fedora 44.
- Recommend plymouth-theme-aurora, so updated installs get the Aurora splash.

* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.134.222-6.aurora3
- Fix renderer keyboard removal and script keyboard lifetime, on top of
  the plymouth-start ordering of 26.134.222-6.aurora2.

* Mon Nov 02 2026 Ryan Murray <ryan@aurorasilicon.org> - 24.004.60-24.aurora1
- Retain Fedora 44's source and patches with the keyboard lifetime fix and
  the plymouth-start ordering.

* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.134.222-6.aurora2
- Order plymouth-start.service after systemd-udevd.service and
  dracut-pre-trigger.service instead of systemd-udev-trigger.service, so
  the splash no longer waits for the coldplug to be queued

* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 26.134.222-6.aurora1
- Keep terminal keyboard reads nonblocking with a separate input descriptor
- Run a PTY regression covering stale readiness and canonical input
