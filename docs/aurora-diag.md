# aurora-diag

`aurora-diag` is the bring-up and regression tool for Aurora on Apple
silicon. It lists sensors, clocks, hardware blocks, services and the GPU
APIs, says what works and what does not, and has `check`, `snapshot`,
`diff` and `report` commands for comparing kernels. `aurora-panic-log`
prints the last panic iBoot kept for the next OS and any kdump crash
dumps. Source: https://github.com/aurora-silicon/aurora-diag (MIT).

The package is opt-in. No image, meta package or other package installs
it. Install it with `sudo dnf install aurora-diag`. It needs only
python3; the dashboard uses python3-textual and some sections read
vulkaninfo, eglinfo/glxinfo, amixer, iw, smartctl, bluetoothctl and gdbus
when they are present. These are weak dependencies.

ALARM (`pacman -S aurora-diag`) and NixOS (`aurora.diag.enable = true`
or `pkgs.aurora-diag`) package the same commit and run the same
`make check` suite during the build.

## Updating the pin

`sources.json` pins the commit, version and SHA-256 of the GitHub
archive. To move to a new commit, set `commit`, `version`, `source_url`,
`archive_root` and `sha256` there, then set `%global commit`, `Version`
and a changelog entry in `packages/aurora-diag/aurora-diag.spec`. The
hash is that of
`https://codeload.github.com/aurora-silicon/aurora-diag/tar.gz/<commit>`.
`tests/test_specs.py` checks that the spec and the pin agree.
