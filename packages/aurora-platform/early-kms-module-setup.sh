#!/bin/bash
# Coldplug the display before everything else in the initramfs.
#
# On Fedora 45 (systemd 262) the initramfs coldplug queues about 2200
# uevents, the "module" subsystem first, and the root filesystem is ready
# long before udev gets to the platform devices. The initramfs pivots with
# the display-subsystem, the DCPs and even simpledrm's card0 still queued:
# appledrm, which is in the initramfs, never loads there, and Plymouth only
# sees an uninitialized simpledrm card. The splash then first appears once
# udev on the real root reaches it, 7.5 s into the boot on a J700.

check() {
    return 0
}

depends() {
    return 0
}

installkernel() {
    hostonly='' instmods appledrm
}

install() {
    inst_hook pre-trigger 20 "$moddir/aurora-early-kms.sh"
}
