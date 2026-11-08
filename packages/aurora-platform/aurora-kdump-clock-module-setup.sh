#!/bin/bash
# dracut module aurora-kdump-clock, used only in kdump's crash kernel
# initramfs (99-zz-aurora.conf in /usr/lib/kdump/dracut.conf.d adds it).
# The crash kernel cannot restart the SMC, so its RTC (rtc0) is missing and
# the kernel never sets the clock. kdump would then date the dump directory
# from the epoch. The PMU RTC still works and keeps UTC, as rtc0 does.

check() {
    return 255
}

depends() {
    return 0
}

install() {
    inst_multiple hwclock
    inst_hook pre-mount 01 "$moddir/aurora-kdump-clock.sh"
}
