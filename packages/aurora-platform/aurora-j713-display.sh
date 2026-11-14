#!/usr/bin/sh
# dracut pre-trigger hook, before aurora-early-kms.sh queues the display.
#
# On M4 (T8132) Macs the kernel leaves the internal display's two DARTs,
# which the running DCP firmware (SID23) and the scanout frontend
# (SID0/SID16) still use, untouched at boot. It admits them only once
# userspace, with the watchdog armed, sets apple_dart.j713_dcp and
# apple_dart.j713_display (named after the first machine, the J713 Air).
# Without that the DCP fails with "inherited SID23 domain not qualified",
# appledrm never registers its card and the desktop has no display
# (aurora-silicon/linux#1704).
#
# Arm the SoC watchdog (30 s), set both, probe the DCP DART and then the
# display DART, in the order the kernel uses when both are set on the command
# line, and stop the watchdog. If a probe hangs the Mac, the watchdog resets
# it instead of leaving it black. Nothing happens on other Macs, when the
# DARTs are already bound (both set on the command line) or with
# aurora.j713_display=0. The kernel still decides: a DART off its qualified
# firmware stays unbound.

aurora_j713_display() {
    local params=/sys/module/apple_dart/parameters
    local devs=/sys/bus/platform/devices
    local dcp disp compat state

    # NUL-separated strings; read drops the NULs without a warning.
    read -r compat < /proc/device-tree/compatible 2>/dev/null || :
    strstr "$compat" "apple,t8132" || return 0
    getargbool 1 aurora.j713_display || return 0
    [ -w "$params/j713_dcp" ] && [ -w "$params/j713_display" ] || return 0
    for dcp in "$devs"/30a340000.*; do break; done
    for disp in "$devs"/30a300000.*; do break; done
    [ -e "$dcp" ] && [ -e "$disp" ] || return 0
    [ -e "$dcp/driver" ] && [ -e "$disp/driver" ] && return 0

    # In a subshell: a failed open must not end the hook's shell, and the
    # watchdog stays armed only while the subshell holds it.
    if ! (
        exec 9>/dev/watchdog0 || exit 1
        echo 1 > "$params/j713_dcp"
        echo 1 > "$params/j713_display"
        for dev in "$dcp" "$disp"; do
            [ -e "$dev/driver" ] || printf '%s' "${dev##*/}" > /sys/bus/platform/drivers_probe
        done
        # Magic close: stop the watchdog.
        printf V >&9
        exec 9>&-
    ); then
        warn "aurora: M4 display: could not arm the watchdog; display DARTs left untouched"
        return 0
    fi

    if [ -e "$dcp/driver" ] && [ -e "$disp/driver" ]; then
        state=$(cat "$disp/j713_display_state" 2>/dev/null)
        info "aurora: M4 display DARTs admitted${state:+ ($state)}"
    else
        warn "aurora: M4 display DARTs were not admitted; see the apple-dart lines in the kernel log"
    fi
}

aurora_j713_display
