// SPDX-License-Identifier: GPL-2.0-or-later
// A force click in Files opens the preview of the item under the pointer.
//
// hid-magicmouse reports the deep stage of a Force Touch click as a key on a
// "<trackpad> Force Click" input device (KEY_INFO, keysym XF86Info). The first
// stage is an ordinary click, so by the time the deep stage arrives Files has
// selected the item under the pointer. Files opens the previewer (sushi) for
// the selection on Space; send Space to it, and only to it.
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const FILES = ['org.gnome.Nautilus', 'org.gnome.nautilus'];

export default class ForceClickPreview extends Extension {
    enable() {
        this._settings = this.getSettings();
        const seat = global.stage.context.get_backend().get_default_seat();
        this._keyboard = seat.create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        Main.wm.addKeybinding('force-click', this._settings,
            Meta.KeyBindingFlags.IGNORE_AUTOREPEAT,
            Shell.ActionMode.NORMAL,
            () => this._forceClick());
    }

    disable() {
        Main.wm.removeKeybinding('force-click');
        this._keyboard = null;
        this._settings = null;
    }

    _forceClick() {
        const window = global.display.focus_window;
        if (!window || !FILES.includes(window.get_wm_class()))
            return;
        const now = GLib.get_monotonic_time();
        this._keyboard.notify_keyval(now, Clutter.KEY_space, Clutter.KeyState.PRESSED);
        this._keyboard.notify_keyval(now + 1, Clutter.KEY_space, Clutter.KeyState.RELEASED);
    }
}
