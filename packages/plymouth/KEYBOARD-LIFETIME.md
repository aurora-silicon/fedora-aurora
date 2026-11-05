# Script splash keyboard lifetime

A renderer can disappear while the script splash is running. In Plymouth
24.004.60, `free_keyboards_for_renderer()` frees its keyboard without calling
`keyboard_removed_handler`. The daemon's `on_keyboard_removed()` therefore
never detaches the splash. `stop_script_animation()` later calls
`ply_keyboard_remove_input_handler()` through the freed pointer, which walks
freed list storage in `ply_list_get_first_node()`.

This is a Plymouth ownership bug. Switching Aurora 1-1 from `ModuleName=two-step`
to `ModuleName=script` in 1-2 exposes it. The script's caps-lock calls expose
another stale reference: `script_lib_plymouth_setup()` saves the keyboard,
but the old `set_keyboard()` and `unset_keyboard()` never update that copy.
The caps-lock native function also accepts a null keyboard without checking it.
Plymouth 26.134.222 has the same affected code, so a clean run on that version
does not prove the lifetime is safe.

`Window.GetWidth(i)` returns script null for an absent display. Aurora's loop
stops there. A script splash started with no pixel displays is rejected by
`show_splash_screen()` before the script runs. Neither those indexed Window
calls nor `DeviceScale=1` frees a keyboard. Static headless startup alone does
not exercise the renderer-loss path.

## Fix

`0001-Fix-splash-keyboard-lifetime.patch`:

- Notify the daemon before freeing a renderer keyboard.
- Detach the script input handler while the old keyboard is alive and update
  the caps-lock library's reference on attach, replacement, and detach.
- Return caps-lock off while no keyboard is attached.
- Preserve the selected keyboard across hide/show and clear the destroyed
  script library pointer.
- Clear the wrapper's detached reference and select a surviving keyboard in
  the daemon when a renderer is removed.

The same patch applies to both version carries. `plymouth.spec` selects
Fedora 44's 24.004.60-24 recipe and original Fedora patches on Fedora 44,
and the existing Fedora 45 recipe elsewhere. Both versions include the terminal input carry. Build either with `scripts/build-rpm plymouth` in the
corresponding Fedora environment.

The fixed script subpackage provides `plymouth(script-keyboard-lifetime) = 1`.
Aurora 1-4 requires it, tying the theme to both patched core libraries and the
patched script plugin through Fedora's existing exact-version dependencies.
The theme drops caps-lock polling entirely. The remaining Plymouth calls
register callbacks or read the splash mode and do not access a keyboard.
The Plymouth patch is still required for safe hide.

## Regression checks

`%check` runs `check-keyboard-lifetime.sh` against the just-built libraries.
`test-keyboard-lifetime.c` uses the real X11 renderer under Xvfb, removes its
last renderer through the device manager, then hides the splash. It checks
removal notification and empty device lists. `test-script-keyboard.c` exercises
native caps-lock queries without a keyboard, late attachment, replacement,
removal of an old keyboard, detach/free, and hide/show. It checks that input
handlers are removed and reattached exactly once.

The tests include private implementation files to reach the lifecycle paths
without a GPU or udev injection. Their renderer and label paths point at the just-built
modules, with a private PTY and font available for the graphical fixture. No test code or display instrumentation is installed in the RPM.

## Source provenance

- [Plymouth 24.004.60 source](https://gitlab.freedesktop.org/plymouth/plymouth/-/tree/d6e6366d622962dce02d8c7e4ab814f54a202509),
  particularly `src/libply-splash-core/ply-device-manager.c:153`,
  `src/main.c:1087`, `src/plugins/splash/script/plugin.c:312`, and
  `src/plugins/splash/script/script-lib-plymouth.c:97`.
- [Plymouth 26.134.222 source](https://gitlab.freedesktop.org/plymouth/plymouth/-/tree/1aacf818fd5d1b6a7695546eb08fcbc46893dd0b)
  carries the same ownership paths.
- [Fedora 44 recipe](https://src.fedoraproject.org/rpms/plymouth/tree/15411610141da34ddb6b4b34ca11fe8d5a63d5e6),
  imported from Fedora's `plymouth-24.004.60-24.fc44.src.rpm`.
  The original archive and spinner update are pinned in `sources.json` and
  match Fedora's published SHA-512 lookaside hashes. Sources and patches are
  GPL-2.0-or-later. The F44 race backport retains its own filename because its
  patch context differs from F45's copy.

## Other distribution carries

ALARM and NixOS apply the same patch and run both native fixtures alongside
terminal-input checks. ALARM exposes `plymouth-script-keyboard-lifetime=1`
through pacman's capability syntax; NixOS exposes `scriptKeyboardLifetime = 1`
on the derivation and asserts it when constructing the theme. Their theme
packages require capability 1, with version 1-4.

## Installation and rollback

Install the complete matching Plymouth subpackage set and theme 1-4 in one
transaction. Rebuild the distribution's initramfs so it contains the patched
core libraries, script plugin, and theme. Installing only the noarch theme
cannot repair a dangling C pointer. Keep the previous RPMs, configuration,
and initramfs for rollback. Reinstall the previous packages and restore the
saved configuration and initramfs if rollback is required.

Retire the capability dependency when distribution packages guarantee this
lifetime contract, after verifying renderer removal and hide/show there.
