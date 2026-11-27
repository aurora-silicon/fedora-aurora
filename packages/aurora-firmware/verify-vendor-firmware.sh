#!/bin/sh
# SPDX-License-Identifier: MIT
# A signed boot binds the vendor firmware archive: the UKI's command line,
# which its signature covers, carries aurora.vendorfw=sha256:<digest>, or
# aurora.vendorfw=none when no archive was trusted (aurora-secboot uki build).
# The ESP is outside that signature, and Asahi's pre-udev 10 loader unpacks
# its archive into / as found, so on such a boot this hook runs first and
# unpacks only a private copy whose digest matches. It always leaves
# /vendorfw behind, which the Asahi loader takes as already loaded; after a
# refusal it is empty and no peripheral that needs the archive is admitted.
# A boot without the parameter is not signed (GRUB) and keeps the Asahi
# loader: whoever can write the ESP controls that boot anyway.

# shellcheck source=/dev/null
type getarg > /dev/null 2>&1 || . /lib/dracut-lib.sh

aurora_nvme_ready() {
    for disk in "$1"/sys/bus/platform/drivers/nvme-apple/*.nvme/nvme/nvme*/nvme*n1/; do
        [ -e "$disk" ] && return 0
    done
    return 1
}

# A subshell: dracut sources every hook into one shell, which has its own
# root and other variables.
aurora_verify_vendorfw() (
    root=${AURORA_INITRD_ROOT:-}
    expected=$(getarg aurora.vendorfw=) || return 0
    esp=$root/run/.system-efi
    copy=$root/run/.aurora-vendorfw.cpio
    rm -rf "$root/vendorfw" "$copy"
    mkdir -p "$root/vendorfw"

    digest=
    case $expected in
        sha256:*) digest=${expected#sha256:} ;;
    esac
    case $digest in
        *[!0-9a-f]*) digest= ;;
    esac
    if [ ${#digest} -ne 64 ]; then
        echo "<3>Aurora: this signed boot trusts no vendor firmware archive (aurora.vendorfw=$expected); not using the one on the ESP" >&2
        return 0
    fi

    if [ ! -e "$root/proc/device-tree/chosen/asahi,efi-system-partition" ]; then
        info ":: Aurora: no asahi,efi-system-partition; vendor firmware will not be loaded"
        return 0
    fi
    modprobe apple-mailbox
    modprobe nvme-apple
    for _ in $(seq 0 50); do
        aurora_nvme_ready "$root" && break
        sleep 0.1
    done
    if ! aurora_nvme_ready "$root"; then
        warn ":: Aurora: timed out waiting for the NVMe device; vendor firmware not loaded"
        return 0
    fi
    if ! (
        # shellcheck source=/dev/null
        . "$root/usr/share/asahi-scripts/functions.sh"
        mount_sys_esp "$esp"
    ); then
        warn ":: Aurora: cannot mount the system ESP; vendor firmware not loaded"
        return 0
    fi
    if [ ! -s "$esp/vendorfw/firmware.cpio" ]; then
        umount "$esp"
        echo '<4>Aurora: the ESP has no vendor firmware; admitting peripherals without it' >&2
        return 0
    fi
    # Check, then unpack, the same bytes: a private copy, not the ESP file
    # read a second time.
    if ! cp -- "$esp/vendorfw/firmware.cpio" "$copy"; then
        umount "$esp"
        rm -f "$copy"
        echo '<3>Aurora: cannot read the vendor firmware on the ESP; not using it' >&2
        return 0
    fi
    umount "$esp"
    actual=$(sha256sum < "$copy")
    if [ "sha256:${actual%% *}" != "$expected" ]; then
        rm -f "$copy"
        echo '<3>Aurora: the vendor firmware on the ESP does not match the digest in this signed boot; not using it' >&2
        return 0
    fi
    (cd "$root/" && cpio --quiet -i < "$copy")
    rm -f "$copy"
    info ":: Aurora: unpacked the vendor firmware this signed boot binds"
)

aurora_verify_vendorfw
unset -f aurora_verify_vendorfw aurora_nvme_ready
