# speakerguardd v2

speakerguardd v2 is installed beside the legacy protection (speakersafetyd,
speakerguardd 0.1), which stays installed and keeps the speakers until a
switch, and keeps any Mac whose self-check refuses:

```sh
sudo aurora-speaker-upgrade --check    # dry run: collect, compile and self-check; nothing stored or switched
sudo aurora-speaker-upgrade            # switches only if this Mac's self-check passes
sudo aurora-speaker-upgrade status
sudo aurora-speaker-upgrade --revert   # back to the legacy protection (--purge also removes the stored tuning)
```

The `aurora-speaker-upgrade` boot unit runs the same switch at boot without
a prompt; a refusal is recorded and not retried until the kernel,
speakerguardd v2 or the tool changes.

The boot unit is enabled by preset, and moves only a speaker whose protected
playback rows are on record. A revert alone is undone at the next boot, so to
stay on the legacy protection also turn the boot unit off:

```sh
sudo aurora-speaker-upgrade --revert
sudo systemctl disable aurora-speaker-upgrade.service   # or mask it
```

The upgrade to aurora-speaker-upgrade 0.1-0.27 applies the preset once, so
a unit that was disabled before it is enabled again; a mask stays. Disable
it again after that upgrade to keep the legacy protection.
