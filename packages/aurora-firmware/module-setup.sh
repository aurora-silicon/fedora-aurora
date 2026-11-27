#!/bin/bash
check() { return 0; }
depends() { echo asahi-firmware; }
installkernel() { instmods aop mt7932-fullmac mt7932_bt_pcie dockchannel-hid; }
install() {
  inst_multiple /usr/libexec/aurora/peripheral-firmware modprobe grep cp rm mkdir cpio sha256sum seq sleep umount
  inst_simple /usr/lib/modprobe.d/aurora-firmware-order.conf
  # Before Asahi's pre-udev 10 loader, which unpacks the ESP's archive as found.
  inst_hook pre-udev 05 "$moddir/verify-vendor-firmware.sh"
  inst_hook pre-udev 20 "$moddir/admit-peripherals.sh"
}
