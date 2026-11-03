#!/usr/bin/sh
# dracut pre-trigger hook: runs after systemd-udevd starts and before
# systemd-udev-trigger coldplugs every device.
#
# Trigger the Apple display subsystem, its DCPs and the DRM devices first, so
# that udev loads appledrm through the normal modalias rules (modprobe.d and
# rd.driver.blacklist= still apply) and initializes the DRM cards before the
# rest of the coldplug queue. Wait for these events only: Plymouth starts
# once systemd-udev-trigger finishes and must find an initialized KMS device.

udevadm trigger --action=add --subsystem-match=platform \
    --attr-match='modalias=*Capple,display-subsystem*'
udevadm trigger --action=add --subsystem-match=platform \
    --attr-match='modalias=*Capple,dcp*'
udevadm settle --timeout=5
udevadm trigger --action=add --subsystem-match=drm --settle
