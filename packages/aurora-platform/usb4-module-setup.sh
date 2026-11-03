#!/bin/bash
# dracut-asahi carries the Type-C port controllers (tps6598x, sn201202x).
# Carry their USB4/Thunderbolt router as well, so that the ports find it when
# they probe rather than after the root filesystem is mounted.

check() {
    return 0
}

depends() {
    return 0
}

installkernel() {
    hostonly='' instmods thunderbolt_apple
}
