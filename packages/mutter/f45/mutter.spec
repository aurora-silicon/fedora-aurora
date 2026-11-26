%global lcms2_version 2.6
%global colord_version 1.4.5
%global glib_version 2.81.1
%global gobject_introspection_version 1.41.4
%global gtk3_version 3.19.8
%global gtk4_version 4.14.0
%global gsettings_desktop_schemas_version 51~rc
%global pixman_version 0.42
%global libei_version 1.3.901
%global wayland_server_version 1.26
%global wayland_protocols_version 1.48
%global libinput_version 1.31.0
%global libdrm_version 2.4.118
%global pipewire_version 1.6.0

%global mutter_api_version 51

%global major_version 51
%global tarball_version %{version}

Name:          mutter
Version:       51.1
Release:       25%{?dist}.aurora
Summary:       Window and compositing manager based on Clutter

# Automatically converted from old format: GPLv2+ - review is highly recommended.
License:       GPL-2.0-or-later
URL:           http://www.gnome.org
Source0:       http://download.gnome.org/sources/%{name}/%{major_version}/%{name}-%{tarball_version}.tar.xz

# Fedora 45 / GNOME 51 only. Fedora 44 keeps the parent recipe.
%if 0%{?fedora} < 45
%{error:This recipe requires Fedora 45 or newer}
%endif

Patch0:        0001-wayland-touch-Do-not-crash-on-empty-focus-surface.patch
Patch1:        0001-native-output-kms-Prefer-variable-refresh-rate-on-VRR-capable-outputs.patch
Patch2:        0002-input-capture-disable-on-eis-disconnect.patch
Patch3:        0003-x11-assign-frame-counters-on-actor-views.patch
Patch4:        0004-backends-take-the-pq-reference-white-from-pq-reference-luminance.patch
Patch5:        0005-onscreen-native-use-variable-refresh-rate-on-the-whole-desktop-of-built-in-panels.patch
Patch6:        0006-renderer-native-drop-power-save-page-flip-onscreens-on-dispose.patch
Patch7:        0007-clutter-frame-clock-update-now-when-even-the-minimum-estimate-is-too-late.patch
Patch10:       0010-wayland-Add-the-wlr-layer-shell-unstable-v1-protocol.patch
Patch11:       0011-wayland-Implement-wlr-layer-shell-unstable-v1.patch
Patch12:       0012-wayland-layer-shell-Wait-for-the-configure-ack-acros.patch
Patch13:       0013-wayland-Support-xdg_popups-parented-to-layer-surface.patch
Patch14:       0014-wayland-layer-shell-Destroy-the-layer-surface-resour.patch
Patch15:       0015-wayland-layer-shell-Stack-layer-surfaces-with-the-sh.patch
Patch16:       0016-wayland-Add-the-wlr-foreign-toplevel-management-unst.patch
Patch17:       0017-wayland-Implement-wlr-foreign-toplevel-management-un.patch
Patch18:       0018-wayland-Add-the-wlr-data-control-unstable-v1-protoco.patch
Patch19:       0019-wayland-Implement-wlr-data-control-unstable-v1.patch
Patch20:       0020-wayland-data-control-Pass-the-receive-fd-straight-to.patch
Patch21:       0021-wayland-Add-the-wlr-gamma-control-unstable-v1-protoc.patch
Patch22:       0022-color-device-Allow-a-client-gamma-ramp-to-override-t.patch
Patch23:       0023-wayland-Implement-wlr-gamma-control-unstable-v1.patch
Patch24:       0024-tests-Add-wlr-gamma-control-tests.patch
Patch25:       0025-wayland-gamma-control-Program-the-ramp-as-a-CTM-with.patch
Patch26:       0026-wayland-Add-the-xdg-decoration-unstable-v1-protocol.patch
Patch27:       0027-wayland-Implement-xdg-decoration-unstable-v1.patch
Patch28:       0028-compositor-Draw-server-side-decorations-for-Wayland-.patch
Patch29:       0029-clutter-stage-view-Apply-a-per-channel-gamma-LUT-in-.patch
Patch30:       0030-color-device-Apply-ramps-the-CRTC-cannot-take-in-the.patch
Patch31:       0031-tests-Read-back-gamma-ramps-applied-in-the-composito.patch
Patch32:       0032-wayland-Add-the-wlr-output-management-unstable-v1-pr.patch
Patch33:       0033-context-main-Allow-several-modes-per-virtual-monitor.patch
Patch34:       0034-wayland-Implement-wlr-output-management-unstable-v1.patch
Patch35:       0035-tests-Add-wlr-output-management-tests.patch
Patch36:       0036-wayland-Add-the-wlr-screencopy-unstable-v1-protocol.patch
Patch37:       0037-wayland-Implement-wlr-screencopy-unstable-v1.patch
Patch38:       0038-wayland-screencopy-Capture-into-linux-dmabuf-buffers.patch
Patch39:       0039-tests-Add-wlr-screencopy-tests.patch
Patch40:       0040-wayland-Add-the-tearing-control-v1-protocol.patch
Patch41:       0041-wayland-Implement-tearing-control-v1.patch
Patch42:       0042-clutter-frame-clock-Add-a-tearing-mode.patch
Patch43:       0043-compositor-native-Decide-per-view-whether-to-tear.patch
Patch44:       0044-kms-Support-asynchronous-page-flips.patch
Patch45:       0045-onscreen-native-Flip-asynchronously-when-the-view-te.patch
Patch46:       0046-tests-Add-tearing-control-tests.patch
Patch47:       0047-wayland-activation-Add-honor-activation-focus-to-foc.patch
Patch48:       0048-prefs-Default-check-alive-timeout-to-20-seconds.patch
Patch49:       0049-wayland-Add-the-ext-session-lock-v1-protocol.patch
Patch50:       0050-wayland-Implement-ext-session-lock-v1.patch
Patch51:       0051-wayland-keyboard-Let-the-event-handlers-focus-a-newl.patch
Patch52:       0052-tests-Add-ext-session-lock-v1-tests.patch
Patch53:       0053-wayland-input-Keep-the-pinned-handler-s-focus-under-.patch
Patch54:       0054-wayland-session-lock-Keep-the-lock-above-restacked-s.patch
Patch55:       0055-wayland-foreign-toplevel-Freeze-the-toplevel-list-wh.patch
Patch56:       0056-wayland-session-lock-Keep-captures-from-showing-what.patch
Patch57:       0057-tests-Add-session-lock-capture-window-list-and-grab-.patch
Patch58:       0058-backends-backlight-sysfs-Perceptual-CIE-1931-scale-for-linear-backlights.patch
# Aurora: apply org.gnome.desktop.peripherals.touchpad scroll-speed to finger scrolling
Patch59:       0059-backends-native-Apply-the-touchpad-scroll-speed-sett.patch
# Upstream 5bdc78fd (MR !5432): ref-white backlight use-after-free on monitor hotplug
Patch60:       0060-backlight-ref-white-Fix-use-after-free-on-monitor-hotplug.patch

BuildRequires: cvt
BuildRequires: desktop-file-utils
BuildRequires: mesa-libEGL-devel
BuildRequires: mesa-libGLES-devel
BuildRequires: mesa-libGL-devel
BuildRequires: mesa-libgbm-devel
BuildRequires: pam-devel
BuildRequires: pkgconfig(bash-completion)
BuildRequires: pkgconfig(colord) >= %{colord_version}
BuildRequires: pkgconfig(glib-2.0) >= %{glib_version}
BuildRequires: pkgconfig(gobject-introspection-1.0) >= %{gobject_introspection_version}
BuildRequires: pkgconfig(sm)
BuildRequires: pkgconfig(lcms2) >= %{lcms2_version}
BuildRequires: pkgconfig(libadwaita-1)
BuildRequires: pkgconfig(libwacom)
BuildRequires: pkgconfig(xkbcommon)
BuildRequires: pkgconfig(glesv2)
BuildRequires: pkgconfig(graphene-gobject-1.0)
BuildRequires: pkgconfig(libdisplay-info)
BuildRequires: pkgconfig(libpipewire-0.3) >= %{pipewire_version}
BuildRequires: pkgconfig(sysprof-capture-4)
BuildRequires: pkgconfig(libsystemd)
BuildRequires: pkgconfig(umockdev-1.0)
BuildRequires: python3-argcomplete
BuildRequires: python3-docutils
# Bootstrap requirements
BuildRequires: gettext-devel git-core
BuildRequires: pkgconfig(libcanberra)
BuildRequires: pkgconfig(gsettings-desktop-schemas) >= %{gsettings_desktop_schemas_version}
BuildRequires: pkgconfig(gtk4) >= %{gtk4_version}
BuildRequires: pkgconfig(gnome-settings-daemon)
BuildRequires: meson
BuildRequires: pkgconfig(gbm)
BuildRequires: pkgconfig(glycin-2)
BuildRequires: pkgconfig(gnome-desktop-4)
BuildRequires: pkgconfig(gudev-1.0)
BuildRequires: pkgconfig(libdrm) >= %{libdrm_version}
BuildRequires: pkgconfig(libei-1.0) >= %{libei_version}
BuildRequires: pkgconfig(libeis-1.0) >= %{libei_version}
BuildRequires: pkgconfig(libstartup-notification-1.0)
BuildRequires: pkgconfig(wayland-protocols) >= %{wayland_protocols_version}
BuildRequires: pkgconfig(wayland-server) >= %{wayland_server_version}
BuildRequires: sysprof-devel

BuildRequires: pkgconfig(libinput) >= %{libinput_version}
BuildRequires: pkgconfig(pixman-1) >= %{pixman_version}
BuildRequires: pkgconfig(xwayland)

BuildRequires: python3-dbusmock
BuildRequires: pkgconfig(gtk+-3.0)
BuildRequires: pkgconfig(libevdev)
BuildRequires: python3-gobject
BuildRequires: xorg-x11-server-Xvfb
BuildRequires: xorg-x11-xauth
BuildRequires: pipewire
BuildRequires: pipewire-pulseaudio
BuildRequires: wireplumber
BuildRequires: mesa-dri-drivers
BuildRequires: dbus-daemon
BuildRequires: xkeyboard-config
BuildRequires: google-noto-sans-fonts

Requires: gnome-control-center-filesystem
Requires: glib2%{?_isa} >= %{glib_version}
Requires: gsettings-desktop-schemas%{?_isa} >= %{gsettings_desktop_schemas_version}
Requires: gnome-settings-daemon
Requires: gtk4%{?_isa} >= %{gtk4_version}
Requires: libeis%{?_isa} >= %{libei_version}
Requires: libinput%{?_isa} >= %{libinput_version}
Requires: pipewire%{_isa} >= %{pipewire_version}
Requires: startup-notification
Requires: dbus
Requires: python3-argcomplete

# Need common
Requires: %{name}-common = %{version}-%{release}

Recommends: mesa-dri-drivers%{?_isa}

Provides: firstboot(windowmanager) = mutter

# Cogl and Clutter were forked at these versions, but have diverged
# significantly since then.
Provides: bundled(cogl) = 1.22.0
Provides: bundled(clutter) = 1.26.0

Conflicts: mutter < 45~beta.1-2

# Make sure dnf updates gnome-shell together with this package; otherwise we
# might end up with broken gnome-shell installations due to mutter ABI changes.
Conflicts: gnome-shell < 51~rc

%description
Mutter is a window and compositing manager that displays and manages
your desktop via OpenGL. Mutter combines a sophisticated display engine
using the Clutter toolkit with solid window-management logic inherited
from the Metacity window manager.

While Mutter can be used stand-alone, it is primarily intended to be
used as the display core of a larger system such as GNOME Shell. For
this reason, Mutter is very extensible via plugins, which are used both
to add fancy visual effects and to rework the window management
behaviors to meet the needs of the environment.

%package common
Summary: Common files used by %{name} and forks of %{name}
BuildArch: noarch
Conflicts: mutter < 45~beta.1-2

%description common
Common files used by Mutter and soft forks of Mutter

%package devel
Summary: Development package for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: libei%{?_isa} >= %{libei_version}
# for EGL/eglmesaext.h that's included from public cogl-egl-defines.h header
Requires: mesa-libEGL-devel

%description devel
Header files and libraries for developing Mutter plugins. Also includes
utilities for testing Metacity/Mutter themes.

%package  tests
Summary:  Tests for the %{name} package
Requires: %{name}-devel%{?_isa} = %{version}-%{release}
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: gtk3%{?_isa} >= %{gtk3_version}
Requires: libei%{?_isa} >= %{libei_version}

%description tests
The %{name}-tests package contains tests that can be used to verify
the functionality of the installed %{name} package.

%package devkit
Summary: Mutter Development Kit
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devkit
Viewer for nested mutter instances.

%prep
%autosetup -S git -n %{name}-%{tarball_version}

%build
%meson -Dtests=enabled
%meson_build

%install
%meson_install

%find_lang %{name}

%check
# The unprivileged upstream suites use mock services and software rendering.
# KMS/TTY tests require hardware and are not enabled in an arm64 RPM builder.
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export XDG_RUNTIME_DIR=$(mktemp -d)
# RPM removes BUILD after success; retain detailed logs outside that tree.
log_dir=$(mktemp -d "%{_topdir}/test-logs.XXXXXX")
trap 'status=$?; cp -a "%{_vpath_builddir}/meson-logs/." "$log_dir/"; rm -rf "$XDG_RUNTIME_DIR"; exit "$status"' EXIT
# Timing-dependent tests that flake on shared CI runners under xvfb (failed
# in turn across reruns of the same sources, passed on others): skip them,
# as Fedora does for flaky tests. Every other test still gates the build.
flaky='input-capture wayland-keyboard sloppy-focus-auto-raise closed-transient-no-input-parents-queued-default-focus-destroyed'
# --list prints "suite - project:name" (or a bare name); keep the name.
tests=$(meson test -C %{_vpath_builddir} --no-rebuild --list | awk 'NF {print $NF}' | sed 's/^.*://' | sort -u)
for name in $flaky; do
  grep -qx "$name" <<< "$tests" || { echo "flaky test $name no longer exists" >&2; exit 1; }
done
tests=$(grep -vxF -f <(tr ' ' '\n' <<< "$flaky") <<< "$tests")
xvfb-run -a meson test -C %{_vpath_builddir} --no-rebuild --print-errorlogs --num-processes 8 $tests

%files -f %{name}.lang
%license COPYING
%doc NEWS
%{_bindir}/gdctl
%{_bindir}/gnome-service-client
%{_bindir}/mutter
%{_datadir}/polkit-1/actions/org.gnome.mutter.*.policy
%{_libdir}/lib*.so.*
%{_libdir}/mutter-%{mutter_api_version}/
%exclude %{_libdir}/mutter-%{mutter_api_version}/*.gir
%{_libexecdir}/mutter-backlight-helper
%{_libexecdir}/mutter-x11-frames
%{_mandir}/man1/mutter.1*
%{_mandir}/man1/gdctl.1*
%{_mandir}/man1/gnome-service-client.1*
%{bash_completions_dir}/gdctl

%files common
%{_datadir}/GConf/gsettings/mutter-schemas.convert
%{_datadir}/glib-2.0/schemas/org.gnome.mutter.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.mutter.experimental.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.mutter.wayland.gschema.xml
%{_datadir}/gnome-control-center/keybindings/50-mutter-*.xml
%{_udevrulesdir}/61-mutter.rules

%files devel
%{_includedir}/mutter-%{mutter_api_version}/
%{_libdir}/lib*.so
%{_libdir}/mutter-%{mutter_api_version}/*.gir
%{_libdir}/pkgconfig/*

%files tests
%{_datadir}/installed-tests/mutter-%{mutter_api_version}
%{_datadir}/mutter-%{mutter_api_version}/tests
%{_libexecdir}/installed-tests/mutter-%{mutter_api_version}

%files devkit
%{_datadir}/applications/org.gnome.Mutter.Mdk.desktop
%{_datadir}/glib-2.0/schemas/org.gnome.mutter.devkit.gschema.xml
%{_datadir}/icons/hicolor/*/apps/org.gnome.Mutter.Mdk*
%{_libexecdir}/mutter-devkit

%changelog
* Fri Nov 27 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-25.aurora
- Backport upstream 5bdc78fd (backlight/ref-white: Fix use-after-free on
  monitor hotplug): a monitor removed while a reference-white brightness
  change is pending no longer leaves its idle callback running against
  the freed monitor (gnome-shell SIGSEGV in on_change_ref_white when an
  HDMI monitor re-plugs during login); the test hunk is left out, the
  51.1 test fixture has no reference-white backlight

* Wed Nov 25 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-24.aurora
- Apply the touchpad scroll-speed setting (gsettings-desktop-schemas 51):
  finger scroll deltas from libinput are multiplied by the factor before
  they become events, so clients and their kinetic scrolling follow it;
  wheel and other scroll sources are unchanged, 1.0 is the old behaviour

* Wed Nov 25 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-23.aurora
- Map sysfs backlights with scale=linear perceptually using CIE 1931 L*
  and lower their hardware floor to 1 nit instead of max/100.

* Tue Nov 17 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-22.aurora
- Keep what is behind a session lock out of every capture and window
  list: window screen casts and window screenshots get transparent
  images while locked (one frame recorded at lock and unlock, none
  while a hidden window changes); wlr-screencopy copy_with_damage no
  longer reports the damage of windows behind the lock; the
  wlr-foreign-toplevel list is frozen (no new windows, title changes or
  closes, no list for managers bound while locked, requests ignored)
  and brought up to date on unlock.
- Keep the lock surfaces' keyboard and pointer focus under a stage grab
  taken by something else while locked, and keep the lock above stage
  children raised over it.

* Tue Nov 17 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-21.aurora
- Support ext-session-lock-v1 (ext_session_lock_manager_v1) so screen
  lockers such as swaylock, hyprlock and gtklock can lock the session:
  every output, including outputs added while locked, shows only an
  opaque blank and the lock client's surfaces; locked is sent only once
  that is on screen everywhere; direct scanout is inhibited; input goes
  only to the lock surfaces (VT and layout switching excepted). A lock
  client that dies leaves the session locked until a new one unlocks
  it. Flatpak-sandboxed clients are not offered it.
- Give a keyboard plugged in while locked to the lock surface, not to
  the focused window.

* Tue Nov 17 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-20.aurora
- Add org.gnome.mutter honor-activation-focus (default true): an
  xdg-activation token requested by the focused window activates and
  raises its target even without a matching input serial, so links
  opened from chat apps bring the browser to the front instead of a
  "is ready" notification. Tokens from unfocused windows still only
  demand attention.
- Default org.gnome.mutter check-alive-timeout to 20000 ms so the "not
  responding" dialog stays away during shader compilation and game
  loading screens (0 still disables it).

* Tue Nov 17 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-19.aurora
- Support tearing-control-v1 (wp_tearing_control_manager_v1): fullscreen
  games and other clients that ask for tearing (Vulkan immediate present
  mode) are presented with asynchronous page flips, without waiting for
  vertical blank. New org.gnome.mutter async-tearing setting
  (fullscreen-only by default, always, off). Surfaces that do not ask for
  tearing are unchanged, and drivers without async page flips keep vsync.

* Tue Nov 17 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-18.aurora
- Support wlr-screencopy-unstable-v1 (zwlr_screencopy_manager_v1,
  version 3) so screenshot, recording and color picker tools such as
  grim, slurp + grim, wf-recorder and hyprpicker work: clients copy an
  output, or a region of it, into a wl_shm (XRGB8888) or, on outputs
  without a transform, a linux-dmabuf buffer, with optional cursor and
  damage tracking. Gated by the new org.gnome.mutter.wayland
  allow-screen-capture setting (on by default); Flatpak-sandboxed
  clients are never offered it.

* Tue Nov 17 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-17.aurora
- Support wlr-output-management-unstable-v1 (zwlr_output_manager_v1 v4),
  so wlr-randr, kanshi, way-displays and wdisplays can list the monitors
  and set their mode, position, transform, scale, adaptive sync and
  enabled state. A configuration is applied atomically across all heads
  through the monitor manager (verified like a DisplayConfig request,
  not stored in monitors.xml); test runs the CRTC assignment only.
- --virtual-monitor accepts several comma separated modes.
- Add wayland-output-management tests (listing, test/apply, adaptive
  sync, refused configurations, mirroring, cancel on hotplug).

* Mon Nov 16 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-16.aurora
- Apply gamma ramps the display hardware cannot take in the compositor:
  on outputs without a CRTC gamma LUT (all Apple DCP panels), curved or
  offset wlr-gamma-control ramps and ICC profile VCGT calibration are
  applied exactly in the final blit of the stage view (a per channel 1D
  LUT), instead of being reduced to a CTM white point or dropped. Night
  light now works on outputs with neither a gamma LUT nor a CTM (T8132).
  Linear ramps still use the CTM, and outputs without a ramp paint as
  before (no extra blit, direct scanout kept).

* Mon Nov 16 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-15.aurora
- Support xdg-decoration-unstable-v1 (zxdg_decoration_manager_v1,
  version 2): Wayland apps that ask for server-side decorations (foot,
  Qt, SDL, Electron, kitty, alacritty and other apps written for
  wlroots or KDE) get a Mutter-drawn titlebar with the window title,
  the button-layout buttons and resizable borders, instead of none.
  org.gnome.mutter.wayland decoration-mode can force server-side or
  client-side decorations for these apps. Apps that do not use the
  protocol, such as GTK and libadwaita apps, keep their own titlebars.

* Mon Nov 16 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-14.aurora
- Support wlr-gamma-control-unstable-v1 (zwlr_gamma_control_manager_v1,
  version 1), so color temperature and night light tools that set the
  output gamma ramp (gammastep, wlsunset, wl-gammarelay-rs, redshift's
  Wayland backend) work. The client ramp replaces the night light ramp
  while it is set and the output's own ramp comes back when the client
  lets go. Outputs without a gamma LUT but with a CTM (Apple DCP panels)
  get the ramp's white point as a CTM

* Mon Nov 16 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-13.aurora
- Support wlr-data-control-unstable-v1 (version 2): clipboard managers
  such as cliphist, clipman and wl-clip-persist can read and set the
  clipboard and the primary selection without keyboard focus. Reads of
  a Wayland-owned selection get the reader's fd directly, as on wlroots
  (wl-clip-persist needs this to recognize its own selection).

* Mon Nov 16 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-12.aurora
- Support wlr-foreign-toplevel-management-unstable-v1
  (zwlr_foreign_toplevel_manager_v1, version 3), so task bars, docks and
  window switchers written for it (waybar's wlr/taskbar, wlrctl) can list
  the open windows and activate, close, maximize, minimize and fullscreen
  them

* Mon Nov 16 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-11.aurora
- Update right away when a frame clock update misses the next
  presentation even with the minimum estimate. In a fixed refresh rate
  mode a fullscreen client drawing every frame no longer locks to every
  other refresh cycle (60-85 fps on a 120 Hz panel)

* Mon Nov 16 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-10.aurora
- Stack layer surfaces with the shell's chrome: top anchored bars go below
  the gnome-shell top panel and their exclusive zone adds to the panel's,
  and the overlay layer is drawn above the panel and notification banners

* Mon Nov 16 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-9.aurora
- Support wlr-layer-shell-unstable-v1 (zwlr_layer_shell_v1, version 5), so
  panels, docks, launchers, notification daemons, wallpaper tools, lock
  screens and overlays written for it (waybar, swaybg, swaync,
  gtk-layer-shell apps) run on GNOME

* Fri Nov 13 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-8.aurora
- Drop the onscreens queued for power save page flips when the renderer is
  disposed, before the Cogl display goes away. gnome-shell no longer
  crashes at shutdown when the displays are in power save

* Fri Nov 06 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-7.aurora
- Use variable refresh rate on the whole desktop of a built-in panel in a
  variable refresh rate mode, so an idle desktop lets the panel drop to its
  minimum rate (external outputs keep fullscreen-only VRR)

* Thu Nov 05 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-6.aurora
- Skip four timing-dependent tests that flake on CI runners under xvfb
  (input-capture, wayland-keyboard, sloppy-focus-auto-raise and
  closed-transient-no-input-parents-queued-default-focus-destroyed).

* Mon Nov 02 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-5.aurora
- Take the PQ reference white from the output's PQ_REFERENCE_LUMINANCE
  (HDR reference-white, as in the Fedora 44 and ALARM builds)

* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-4.aurora
- Assign X11 frame counters only on views which paint the window

* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-3.aurora
- Disable active input capture when its EIS client disconnects

* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 51.1-2.aurora
- Rebase the VRR preference and touch null-focus fixes onto GNOME 51
- Build and run the upstream unprivileged test suites on Fedora 45
