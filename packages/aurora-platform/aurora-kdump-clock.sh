#!/bin/sh
# Set the system clock from the first other RTC when rtc0 is missing.
[ -e /dev/rtc0 ] && return 0 2>/dev/null
for rtc in /dev/rtc[1-9]; do
    [ -e "$rtc" ] || continue
    hwclock --hctosys --utc -f "$rtc" 2>/dev/null && break
done
