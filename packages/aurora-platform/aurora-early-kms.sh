#!/usr/bin/sh
# dracut pre-trigger hook: runs after systemd-udevd starts and before
# systemd-udev-trigger coldplugs every device.
#
# Coldplug the Apple display subsystem, its DCPs and their device-link
# suppliers (for example the Type-C PHY that an external DCP drives) first,
# then the DRM devices. udev loads appledrm and the supplier drivers through
# the normal modalias rules, so modprobe.d and rd.driver.blacklist= still
# apply, and the DRM cards are initialized before the rest of the coldplug
# queue. Plymouth starts once systemd-udev-trigger finishes and then finds an
# initialized KMS device.

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

    udevadm trigger --action=add --settle "$@"
    udevadm settle --timeout=5
    udevadm trigger --action=add --subsystem-match=drm --settle
}

aurora_early_kms
