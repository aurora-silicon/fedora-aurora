# J493 legacy speaker recovery kernel

This optional kernel is for the 13-inch M2 MacBook Pro (Apple J493) affected
by the speaker-protection cutover while running Fedora Aurora
`7.3.0-20.fc45.aurora.aarch64`.

It combines the `7.3.0-19` kernel source (`9127278801dd`) with the BCM4378
receive-DMA fix from linux#1078. The resulting source is
`f92b6bc6b736b19921e9f2df91ed8846ab5cd05e`. Its only code difference from
the -19 source is the BCM4378 fix. Audio retains the existing Asahi
`Speaker Volume Unlock` interface, used by `speakersafetyd`; it does not
require extracting a macOS speaker-tuning bundle.

This is a recovery package, not a replacement for the current fleet kernel.
It has a separate package name and module directory, and retains the
installed -20 kernel as a fallback. It does not replace the userpages tool,
disable protection, or edit the speaker daemon's gate.

## Compatibility

The historical kernel uses generation-0 device trees. Kernel -25 and later
use generation 1, so this package conflicts with those kernel-core packages.
Do not remove a working generation-1 kernel to install this recovery build.
This package's install script also refuses machines other than J493.

The current `aurora-audio` package still ships J493's Asahi DSP graph
(`j293/graph-j493.json`). On a legacy-interface kernel, the packaged
`speakerguardd-gate` selects `speakersafetyd` automatically. The v2 packages
can stay installed. Disabling v2 while still running -20 does not restore
the old kernel interface.

## Owner procedure after the signed package is published

First confirm the machine and its retained kernels:

```sh
uname -r
tr '\0' '\n' </sys/firmware/devicetree/base/compatible
rpm -q kernel-aurora-core kernel-aurora-legacy-core
```

On the J493 with the -20 kernel retained, install the optional package:

```sh
sudo dnf install kernel-aurora-legacy
```

Reboot and select the entry whose version ends in `.aurora.legacy.aarch64`
from GRUB for one test boot. Leave the existing -20 entry available.
After boot, check:

```sh
uname -r
sudo /usr/libexec/speakerguardd-v2/speakerguardd-gate explain
systemctl --no-pager status speakersafetyd
nmcli device status
amixer -c AppleJ493 controls | grep -E 'Speaker Volume Unlock|Speaker Protection'
```

Expect the legacy kernel version, a gate result selecting legacy, a running
`speakersafetyd`, working Wi-Fi, and `Speaker Volume Unlock`. Test normal
desktop audio. If the legacy daemon fails, collect its journal rather than
changing amplifier controls:

```sh
journalctl -b -u speakersafetyd --no-pager
```

This build has not been boot-tested on the reporter's J493. A successful
compile and package build alone do not establish hardware recovery.

## Leaving recovery

Keep the known bootable -20 entry. Once a newer kernel with a validated
legacy speaker path is available, boot a working ordinary kernel, remove
`kernel-aurora-legacy`, `kernel-aurora-legacy-core`, and
`kernel-aurora-legacy-modules-extra`, then install the replacement. The
generation-1 conflict prevents an accidental incompatible update while this
historical recovery kernel is retained.
