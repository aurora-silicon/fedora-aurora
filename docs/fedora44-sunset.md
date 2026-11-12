# Fedora 44 sunset

Fedora 45 is now the Aurora Fedora Remix release. Fedora 44 gets no further
Aurora updates, apart from a manual security fix if one is needed.

## For users

- Upgrade to Fedora 45 with `dnf system-upgrade`, as described in
  [Upgrading from Fedora 44 to Fedora 45](upgrade-fedora45.md).
- Systems that stay on Fedora 44 keep working. Their Aurora repository
  (`44/testing` or `44/stable`) stays online at its last snapshot, so dnf
  refreshes and reinstalls keep working, but no new Aurora packages arrive.
  Fedora's own Fedora 44 updates continue until Fedora ends them.
- Fedora 45 has a stable channel (`45/stable/aarch64`). A system on the
  Fedora 44 stable channel upgrades straight to Fedora 45 stable once the
  first Fedora 45 snapshot has been promoted.
- New installs use Fedora 45 images.

## For maintainers

- `rpms.yml` builds Fedora 45 only. A manual run that names packages also
  builds them for Fedora 44, so a security fix can still reach the frozen
  feed through a manual `publish.yml` run with `fedora-release: 44`.
- `publish.yml` and `deploy-snapshot.yml` default to Fedora 45. Automatic
  publication publishes Fedora 45 only, and `publish-fedora45.yml`, which
  followed every Fedora 44 publication with a Fedora 45 one, is gone.
- `promote.yml` takes a `fedora-release` input (default 45) and promotes what
  that release's testing channel served. `channel-site.py` serves
  `45/stable` beside the frozen Fedora 44 channels and keeps every populated
  channel on each deployment.
- `images.yml` builds Fedora 45 images by default, and automatic image builds
  follow Fedora 45 testing deployments. Fedora 44 images are still available on
  request, as `<profile>-f44-candidate`, which the automatic payload workflow
  does not take.
- The Fedora 44 recipes and `packages/*/f45` overlays stay as they are, so
  this change does not rebuild anything. Folding the overlays into the main
  recipes and removing Fedora 44 support from the scripts is separate work.
