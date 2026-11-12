# kdump: saving Linux crashes

iBoot keeps no record of a Linux panic, and DRAM does not survive the
restart, so a Linux crash on Apple silicon normally leaves nothing
behind. kdump fixes that: a second kernel waits in reserved memory, takes
over when Linux panics, writes the crashed kernel's memory and log to
`/var/crash`, and restarts the Mac. `aurora-panic-log` (aurora-diag)
lists the saved dumps.

kdump is opt-in. It reserves crash kernel memory on every boot (320 MiB
on a Mac with 4 to 64 GiB), so no image or meta package installs it.

## Turning it on

    sudo dnf install aurora-platform-kdump
    sudo reboot

Installing the package enables `kdump.service` and adds kdump-utils'
default `crashkernel=` to every boot entry and to `/etc/kernel/cmdline`
(`kdumpctl reset-crashkernel`). The memory is reserved from the next
boot. A `crashkernel=` you set yourself is kept.

To check it after the reboot:

    kdumpctl status                      # "Kdump is operational"
    cat /sys/kernel/kexec_crash_loaded   # 1

To test it, crash the kernel on purpose (this restarts the Mac and loses
unsaved work):

    sync; echo c | sudo tee /proc/sysrq-trigger

After the restart, `/var/crash/127.0.0.1-<date>/` holds `vmcore`,
`vmcore-dmesg.txt` (the crashed kernel's log) and `kexec-dmesg.log` (the
crash kernel's log).

## Turning it off

    sudo dnf remove aurora-platform-kdump
    sudo reboot

This disables `kdump.service` and removes the `crashkernel=` that the
install added.

## What the package changes

- `/usr/lib/kdump/dracut.conf.d/99-zz-aurora.conf`, read only when
  kdump-utils builds the crash kernel's initramfs:
  - adds `nvme_apple`. kdump-utils' own `99-kdump.conf` replaces
    dracut-asahi's module list, so without it the crash kernel has no
    disk.
  - leaves out the drivers of coprocessors and buses the crashed kernel
    left running (GPU, display, Thunderbolt, AOP, PMP, ANE, audio, USB,
    keyboard, I2C, SPI). Probing them in the crash kernel stalled udev
    before `nvme_apple` loaded.
  - builds a plain initramfs instead of a squashfs image behind a busybox
    `/init`. With dracut 108 (Fedora 44) that `/init` never loaded its
    first module in the crash kernel.
  - adds the dracut module `aurora-kdump-clock`. The crash kernel cannot
    restart the SMC, so it has no RTC and would date the dump wrongly; the
    hook sets the clock from the panic time in the crashed kernel's
    vmcoreinfo, or else from the PMU RTC.
- `kdump.service.d/50-aurora-kdump.conf` skips the service, instead of
  failing it, on a boot without crash kernel memory.

The kernel side is in linux-aurora: the crash kernel restarts an NVMe
controller (ANS) the crashed kernel left running on M1 and M2 Macs, arms
the watchdog at its longest timeout so a stuck crash kernel still
restarts the Mac, starts on CPU 0 under a CTXR window (A18 Pro), and may
load while devices keep DMA to retained memory, because the crash kernel
lives in its own reservation.

## Tested Macs

| Mac | Kernel | Result |
|---|---|---|
| MacBook Pro 16" (M1 Pro) | 7.3.0-aurora-fleet67 | Works. sysrq-c: 200 MiB vmcore and both logs saved in 4 s, dump directory dated to the panic second, back on the default kernel 42 s after the panic. |
| MacBook Air (M2) | 7.3.0-aurora-fleet67 | Works. sysrq-c: 222 MiB vmcore and both logs saved, back on the default kernel 17 s after the panic. Before the squashfs layer was dropped from the crash kernel's initramfs, it stalled and the watchdog restarted the Mac after about 3 minutes. |
| MacBook Neo (A18 Pro) | test kernels with aurora-silicon/linux#1200 | Works (two dumps, crash on CPU 0 and on a CTXR-confined core). After one later run the default kernel hung on the next boot; not understood yet. |
| MacBook Pro (M4 Pro) | not tested | |

Other Macs are untested. On a Mac where the crash kernel stalls, a panic
restarts the Mac after about 3 minutes instead of 10 seconds.
