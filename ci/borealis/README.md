# System RPM candidates

This builds the Fedora system Mesa package layout and its matching x86 FEX
provider from one checksum-pinned public Mesa commit. Fedora 44 and 45 builds
run on hosted ARM64 runners; the guest provider runs on hosted x86_64.

The Mesa recipe retains Fedora's upstream packaging and license attribution.
The license clarification correspondence is compressed verbatim and its
original bytes are checksum-verified during preparation.
The source manifest records every downloaded input. Container images and
workflow actions are pinned. No target installation, package-feed publication,
signing key or hardware access is part of this workflow. Candidate packages need
separate hardware qualification before deployment.
# Native qualification overlay mode

Manual runs can set `native_overlay=true` to build one Fedora 45 AArch64
qualification overlay. The default remains the existing native/FEX RPM matrix.
The overlay mode uses the same checksum-pinned public inputs, builds compiler
tools first, then builds Asahi/Zink/Honeykrisp with system compiler tools and
LLVM/SPIRV-Tools disabled in driver runtime dependencies. It checks the source
stamp, ELF architecture and dependencies with Mesa's qualification packager,
carries license notices, and uploads the archive, manifest, checksums and logs.

Use a Mesa source containing `src/asahi/tools/native-gl-qualification/make-overlay.py`.
Building an overlay does not qualify GPU execution or change an installed
system. The normal RPM build remains available without this option.
