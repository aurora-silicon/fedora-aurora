#!/bin/sh
# Set the crash kernel's clock when it has no rtc0: the crash kernel cannot
# restart the SMC, so the SMC RTC is missing. Prefer the time the crashed
# kernel recorded at the panic (CRASHTIME in its vmcoreinfo note, near the
# start of /proc/vmcore); else read another RTC (the PMU RTC on M4-class
# Macs). This file is sourced by dracut: no exit.
if [ ! -e /dev/rtc0 ]; then
    _t=$(head -c 4194304 /proc/vmcore 2> /dev/null | tr -c '[:print:]' '\n' |
        sed -n 's/^CRASHTIME=\([0-9][0-9]*\)$/\1/p' | head -n 1)
    if [ -z "$_t" ] || ! date -u -s "@$_t" > /dev/null 2>&1; then
        for _rtc in /dev/rtc[1-9]; do
            [ -e "$_rtc" ] || continue
            hwclock --hctosys --utc -f "$_rtc" 2> /dev/null && break
        done
    fi
    unset _t _rtc
fi
