#!/bin/bash
check() { return 0; }
depends() { echo asahi-firmware; }
installkernel() { instmods aop mt7932-fullmac mt7932_bt_pcie; }
install() {
  inst_multiple /usr/libexec/aurora/peripheral-firmware modprobe grep
  inst_simple /usr/lib/modprobe.d/aurora-firmware-order.conf
  inst_hook pre-udev 20 "$moddir/admit-peripherals.sh"
}
