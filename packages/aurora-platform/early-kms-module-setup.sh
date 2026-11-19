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

# appledrm registers its DRM device only once every DCP has bound, the
# external ones included, and an external DCP binds only after its Type-C
# PHY, which needs the retimer or PD controller on an I2C bus. Without that
# chain in the initramfs the internal panel's DCP starts in the initramfs,
# stops showing the boot framebuffer, and nothing presents until the real
# root loads the I2C controller: ~4.5 s of black on a J700.
installkernel() {
    hostonly='' instmods appledrm mux-apple-display-crossbar \
        i2c-pasemi-platform phy-apple-atc phy-ti-cd2e22 tps6598x
}

install() {
    inst_hook pre-trigger 20 "$moddir/aurora-early-kms.sh"
}
