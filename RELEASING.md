# Release procedure

Package snapshots, filesystem images, signed installer catalogs and the macOS application have separate identities. Promote a complete, compatible set and keep the previous set available for rollback.

## Build and publish hardware packages

Update the immutable commits, archive roots and SHA-256 values in `sources.json`, then update the affected RPM specs. Kernel modules and device trees must come from the same kernel build. Keep the kernel and Mesa interface compatible when updating either side; the source and package versions alone do not prove that interface agrees.

Run the source checks and request the affected packages on a native AArch64 worker:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 images/test_configure.py
gh workflow run rpms.yml --ref <candidate-branch> -f 'packages=kernel-aurora mesa-aurora'
```

Retain the successful run ID, exact commit and package receipts. Merge the candidate with its original commit ancestry preserved. The publisher accepts successful push/manual runs from this repository only after their commits are merged; it checks the shared builder, recipes, source pins and complete artifact inventories before importing them. Squashing a candidate changes that ancestry and requires another qualifying build.

Publish from `main`, using the previous immutable snapshot for unchanged packages:

```sh
gh workflow run publish.yml --ref main -f deploy=yes
```

With no `build-run`, the workflow picks the newest qualifying build of every package and the newest
snapshot as the base; the explicit `build-run`, `base-release` and `release-tag` inputs still work.
Without `deploy=yes` (or the `AUTO_DEPLOY_TESTING` variable) it publishes the release but leaves the live
feed alone; `deploy-snapshot.yml` deploys it later. Tags start with `testing-` and are never reused. The workflow authenticates the base RPMs, replaces every output of rebuilt source packages, signs the resulting RPMs and repository index, and uploads the packages, manifest, source RPMs and build provenance. The committed public key and `keys/fingerprint.txt` identify the signing authority. Private signing credentials remain in repository secrets.

Check that the deployed [testing feed](https://aurorasilicon.org/fedora-aurora/44/testing/aarch64/) has the new manifest and a valid repository signature before building images. Compare its manifest bytes to the immutable release asset. Retain previous kernel packages and release assets.

## Build and qualify filesystem images

Run each profile against the verified testing feed:

```sh
gh workflow run images.yml --ref main -f profile=fedora-kde
gh workflow run images.yml --ref main -f profile=fedora-gnome
gh workflow run images.yml --ref main -f profile=fedora-minimal
```

Record each run's exact source commit and the signed package snapshot being served during the build. Freeze that feed until all three builds finish. Candidate artifacts expire after 14 days, so copy the required deliverables to their immutable release before they expire.

Inspect the retained package inventory against the signed snapshot manifest. Check the kernel, Mesa, bootloaders, firmware admission, audio protection, first-boot, SEP/libfprint and power-management packages. The initramfs inventory must contain encryption, firmware admission and the required peripheral drivers. KDE also needs the patched system-information package. A successful build or metadata audit establishes image contents, not device behavior.

The [ALARM](https://github.com/aurora-silicon/alarm-aurora) and [NixOS](https://github.com/aurora-silicon/nixos-aurora) repositories implement their own signed package/cache publication and native image workflows. Their images use the same installer payload layout contract. Nix cache activation verifies every signed NAR over HTTP before image builds consume it.

## Pair the installer resources

The `publish-payload.yml` caller pins the shared producer in [aurora-distributions](https://github.com/aurora-silicon/aurora-distributions). Inspect that exact producer revision before dispatching it. Its installer source, runtime release, Recovery template, metadata schemas and catalog engine digest must match the application candidate. Advance the caller pin only after that producer is qualified.

For a compatible producer, pass the completed image run and profile:

```sh
gh workflow run publish-payload.yml --ref main \
  -f profile=fedora-kde -f image-run='<successful-image-run-id>'
```

The producer authenticates the image build, checks filesystem hashes, assembles the payload and signs the exact catalog bytes. Each delivery retains its image/source provenance. Repeat for the other selected profiles and publish the resulting signed profile resources through `aurora-distributions`.

The native application's execution contract has advanced beyond the earlier public runtime. Refreshed image artifacts must be paired with the current runtime and Recovery resources before their catalogs are promoted. Merely running the older pinned producer would publish an incompatible set.

## Produce the macOS installer draft

The native installer source lives in [aurora-installer](https://github.com/aurora-silicon/aurora-installer). Its draft DMG workflow requires an immutable `aurora-distributions` commit whose nine signed catalogs match the candidate's runtime version, digest, filename and size. The app downloads the chosen distribution and resources later; filesystem images and the runtime archive do not belong inside the app bundle.

Qualify the exact candidate through the repository's native macOS build driver, portable checks and packaging gates. Reuse recorded qualification for unchanged source/toolchain identities. Sign with Developer ID, notarize and staple the application and DMG, then attach the result to a draft release. Record source, resource revision, signatures, notarization results and checksums. The source workflow alone does not establish that a DMG was produced or notarized.

## Validate on hardware before promotion

Record a fresh encrypted Fedora KDE installation through the native macOS installer and native Recovery flow, including the real shutdown handoff. Record the image/catalog identities, installed package versions, kernel command line and device-tree source. Check unlock, first-boot account creation, desktop login, reboot and signed system updates.

Validate Wi-Fi, Bluetooth, GPU/display, keyboard/trackpad, microphone, camera, SEP/fingerprint, power reporting and suspend/resume. Check audio device routing and speaker protection while respecting any device-specific instruction against playback. Qualify external-display and dock/Thunderbolt devices separately. Evidence from another distribution or an earlier kernel does not qualify the refreshed Fedora image.

Keep the previous working installation and its rollback evidence until the replacement is ready for device deployment. The current source/build checks are development qualification; the final native installation and hardware gates remain required.

## Restore an update snapshot

New snapshots retain `repository-metadata-<tag>.tar.gz` and its detached signature. The archive contains the exact signed repository index, referenced checksum-verified metadata, manifest and public key. RPMs remain at immutable release URLs.

```sh
gh workflow run deploy-snapshot.yml --ref main -f release-tag='<retained-testing-tag>'
```

The workflow verifies the archive and repository signatures before activation. Verify the live manifest and signed index after deployment. This changes the update feed; it does not downgrade an installed system. Restoring an installed kernel requires selecting the retained kernel and its matching device trees/modules through the boot setup.
