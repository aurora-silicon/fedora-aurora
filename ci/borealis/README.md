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
