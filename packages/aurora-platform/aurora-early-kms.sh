#!/usr/bin/sh
# dracut pre-trigger hook: runs after systemd-udevd starts and before
# systemd-udev-trigger coldplugs every device.
#
# Queue the Apple display subsystem, its DCPs and their device-link
# suppliers (for example the Type-C PHY that an external DCP drives) ahead
# of the rest of the coldplug, so udev loads appledrm and the supplier
# drivers first, through the normal modalias rules (modprobe.d and
# rd.driver.blacklist= still apply), then the DRM cards that exist already
# (the boot framebuffer's simpledrm card), so Plymouth can start on it.
# Do not wait for any of them: the display processors take a second or
# more to start, the external ones included, and the root file system does
# not need them. Plymouth adds appledrm's card from its udev add event when
# the driver registers it.

aurora_early_kms() {
    local dev alias link

    set --
    for dev in /sys/bus/platform/devices/*; do
        [ -r "$dev/modalias" ] || continue
        read -r alias < "$dev/modalias" || continue
        case "$alias" in
            *Capple,display-subsystem*|*Capple,dcp*) ;;
            *) continue ;;
        esac
        set -- "$@" "$(readlink -f "$dev")"
        for link in "$dev"/supplier:*; do
            [ -e "$link/supplier" ] && set -- "$@" "$(readlink -f "$link/supplier")"
        done
    done
    [ $# -gt 0 ] || return 0

    udevadm trigger --action=add "$@"
    udevadm trigger --action=add --subsystem-match=drm
}

aurora_early_kms
