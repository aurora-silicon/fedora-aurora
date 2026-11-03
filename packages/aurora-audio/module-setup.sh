#!/bin/bash
# Fedora's dist-alsa.conf loads snd-seq whenever snd-pcm loads, and appledrm
# brings snd-pcm into the initramfs. Carry snd-seq so that load succeeds there.

check() {
    return 0
}

depends() {
    return 0
}

installkernel() {
    hostonly='' instmods snd-seq
}
