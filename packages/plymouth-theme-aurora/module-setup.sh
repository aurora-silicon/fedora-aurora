#!/bin/bash
# SPDX-License-Identifier: MIT
check() { [[ $(plymouth-set-default-theme 2>/dev/null) == aurora ]]; }
depends() { echo plymouth; }
install() {
    inst_simple /usr/libexec/aurora-plymouth
    inst_multiple od tr cat mkdir mv
    inst_simple /usr/lib/systemd/system/plymouth-start.service.d/aurora-plymouth.conf
    inst_hook pre-trigger 01 "$moddir/prepare.sh"
}
