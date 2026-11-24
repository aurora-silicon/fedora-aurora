# SPDX-License-Identifier: MIT
# Copyright The Asahi Linux Contributors
# Adapted from asahi-scripts functions.sh at 800400dcf961.
mount_sys_esp() {
    local mountpoint=$1 esp_uuid='' bootmnt

    mkdir -p "$mountpoint"
    while mountpoint -q "$mountpoint"; do
        umount "$mountpoint"
    done

    if [[ -r /proc/device-tree/chosen/asahi,efi-system-partition ]]; then
        esp_uuid=$(tr -d '\0' < /proc/device-tree/chosen/asahi,efi-system-partition)
    fi
    if [[ ! -e /boot/efi/.builder && ! -e /boot/.builder && -n $esp_uuid ]]; then
        mount "PARTUUID=$esp_uuid" "$mountpoint"
        return
    fi

    for bootmnt in /boot/efi /boot; do
        if [[ -d $bootmnt/m1n1 ]]; then
            mount --bind "$bootmnt" "$mountpoint"
            return
        fi
    done
    echo 'update-aura: cannot locate the system EFI partition' >&2
    return 1
}
