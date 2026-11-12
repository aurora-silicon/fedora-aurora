#!/bin/bash
# dracut module aurora-kdump-clock, used only in kdump's crash kernel
# initramfs (99-zz-aurora.conf in /usr/lib/kdump/dracut.conf.d adds it).
# The crash kernel cannot restart the SMC, so its RTC (rtc0) is missing and
# the kernel never sets the clock; kdump would then date the dump directory
# wrongly. The hook takes the panic time from the crashed kernel's vmcoreinfo
# (CRASHTIME), or else reads the PMU RTC where there is one (M4 class).

check() {
    return 255
}

depends() {
    return 0
}

install() {
    inst_multiple hwclock head tr sed date
    inst_hook pre-mount 01 "$moddir/aurora-kdump-clock.sh"
}
