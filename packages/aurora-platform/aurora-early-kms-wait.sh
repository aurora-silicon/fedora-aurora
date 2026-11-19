#!/usr/bin/sh
# dracut pre-pivot hook: hand the splash over to the display driver before
# leaving the initramfs.
#
# appledrm registers its DRM device once every display coprocessor is up,
# which can be after the root file system is ready. If the initramfs pivots
# first, udevd is gone when the device appears: Plymouth only hears of it
# from the real root's udevd, about half a second later, and in between an
# external display's hotplug makes the kernel's fbdev emulation, which then
# has no DRM master to defer to, light every output with its own empty
# buffer: the panel flashes black before the splash comes back.
#
# Wait for udev to announce the display subsystem's card, so Plymouth opens
# it (and holds DRM master) while the initramfs udevd still runs. udevadm
# wait returns on udev's own event for the card, or at once if udev has
# announced it already; nothing polls. No wait without the display
# subsystem, or when no driver is bound to it (appledrm absent or
# blacklisted): then nothing will register a card. The wait is bounded at
# 2 s; how long it lasts is how late the kernel registers the card.

aurora_early_kms_wait() {
    local dev

    for dev in /sys/bus/platform/devices/*display-subsystem; do
        [ -e "$dev/driver" ] && break
    done
    [ -e "$dev/driver" ] || return 0

    # 60-drm.rules links each platform card as
    # /dev/dri/by-path/platform-<device>-card.
    udevadm wait --timeout=2 "/dev/dri/by-path/platform-${dev##*/}-card" 2>/dev/null
    return 0
}

aurora_early_kms_wait
