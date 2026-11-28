# speakerguardd v2

speakerguardd v2 is the only speaker protection on every Mac, and the only
program that takes the kernel's speaker interlock. The Asahi stack is gone:
aurora-audio 4.1-18 requires speakerguardd-v2 and aurora-speaker-upgrade,
obsoletes speakersafetyd, speakersafetyd-aurora-profiles, speakerguardd 0.1
and asahi-audio, and installs no Asahi speaker graph. An upgrade removes the
old packages in the same transaction.

`aurora-speaker-upgrade` moves a Mac's speakers to v2 with that Mac's own
tuning:

```sh
sudo aurora-speaker-upgrade --check    # dry run: collect, compile and self-check; nothing stored or switched
sudo aurora-speaker-upgrade            # switches only if this Mac's self-check passes
sudo aurora-speaker-upgrade status
```

The `aurora-speaker-upgrade` boot unit, enabled by preset, runs the same
switch at boot without a prompt, and moves only a speaker whose protected
playback rows are on record; a refusal is recorded and not retried until the
kernel, speakerguardd v2 or the tool changes. A Mac that v2 does not qualify
keeps its speakers at the kernel's floor: there is no automatic fallback to an
older daemon.

## User opt-out (`aurora-speaker-stack`)

Users who explicitly want `speakersafetyd` instead of `speakerguardd` v2 can
switch with one command:

```sh
sudo aurora-speaker-stack select speakersafetyd
```

This records the selection in `/etc/aurora/speaker-stack.conf`, masks the v2
and upgrade units, installs stock `speakersafetyd`, hands over the kernel
speaker interlock where the running kernel exposes the dual interface, and
starts `speakersafetyd.service`. Later package upgrades read
`/etc/aurora/speaker-stack.conf` and preserve the user's choice.

To inspect the current selection or switch back to `speakerguardd` v2:

```sh
aurora-speaker-stack status
sudo aurora-speaker-stack select sgv2
```

See `man 8 aurora-speaker-stack` for details.
