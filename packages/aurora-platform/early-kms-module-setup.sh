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
#
# Every Apple PHY driver goes in, not a list of the ones known today: which
# PHYs a display's DCPs need depends on the SoC (Type-C, USB2 and DPTX PHYs
# on T6041, for example), and an image is built away from the Mac it boots.
installkernel() {
    hostonly='' instmods appledrm mux-apple-display-crossbar \
        i2c-pasemi-platform phy-ti-cd2e22 tps6598x
    hostonly='' instmods '=drivers/phy/apple'
}

install() {
    inst_hook pre-trigger 20 "$moddir/aurora-early-kms.sh"
    inst_hook pre-pivot 90 "$moddir/aurora-early-kms-wait.sh"
    # What the pre-pivot wait runs, and the by-path card link it names.
    inst_multiple modprobe tr udevadm
    inst_rules 60-drm.rules
}
