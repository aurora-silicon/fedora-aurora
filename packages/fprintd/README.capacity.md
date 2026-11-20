# Full Touch ID storage

The Aurora driver maps kernel `ENOSPC` to `FP_DEVICE_ERROR_DATA_FULL`.
The paired fprintd emits the terminal D-Bus status `enroll-data-full` without
listing, deleting, or retrying enrollment. Removal is an explicit user action.
The libfprint RPM requires `fprintd(aurora-no-enroll-gc) >= 1`; do not ship the
new libfprint patch with an older, unguarded fprintd.

## Why the daemon needs a guard

In [fprintd 1.94.5 `src/device.c`](https://gitlab.freedesktop.org/libfprint/fprintd/-/blob/v1.94.5/src/device.c),
`enroll_cb()` handles DATA_FULL by calling `try_delete_print()` if
`FP_DEVICE_FEATURE_STORAGE_LIST` is present. It does not separately check
`STORAGE_DELETE`. The collector lists device prints, subtracts the host gallery,
deletes one remaining print, and retries enrollment. An unknown SEP print can
belong to another operating system, so lack of a host record cannot establish
that it is disposable.

Aurora's class ID is `apple-sep` (`FP_COMPONENT`), not `aurora`. Its class
initializes listing and deletion features from its `list`, `delete`, and
`clear_storage` methods. Patch1005 leaves these capabilities available for
explicit management. fprintd Patch1 checks the driver ID before the feature
check and collector call, so an Aurora DATA_FULL goes straight to
`enroll_result_to_name()` and then `EnrollStatus("enroll-data-full", true)`.
The collector and retry remain unchanged for other drivers.

The earlier fprintd Patch0 already protects the enrollment entry point for
`apple-sep`: reject an existing finger instead of automatically deleting it,
skip first-enrollment storage clearing, and skip pre-enrollment identification
and its duplicate collection path. It also preserves host records when explicit
device deletion fails. These guards remain in place.

## Wording

[GNOME Settings 49](https://github.com/GNOME/gnome-control-center/blob/b171fbe1e0258dd0c8dc9abcd8f12855ed563a36/panels/system/users/cc-fingerprint-dialog.c#L775)
uses its existing translated text: “Fingerprint device storage is full”.
D-Bus enrollment status carries a status name and completion flag, not the
driver's diagnostic text, so this change cannot add a removal instruction to
GNOME without a separate gnome-control-center change.

The fprintd-enroll CLI keeps its machine-readable result line and additionally
prints: “Fingerprint storage is full. Remove an enrolled fingerprint before
trying again.” The driver diagnostic mentions both the finger limit and host
store because the errno does not distinguish them.

[Apple's Touch ID settings guide](https://support.apple.com/guide/mac-help/touch-id-password-settings-mchl319754b3/mac)
says “You can add up to three fingerprints per user account” and documents five
total per Mac. This is documentation wording, not a claim to have captured a
macOS error dialog. Proposed dedicated finger-limit text, once the kernel can
distinguish it: “Fingerprint limit reached. You can add up to three fingerprints.
Remove a fingerprint before adding another.” The current Linux driver/kernel
limit must not be described as Apple's per-user accounting: the kernel checks
its live SEP count against three.

## Capacity errors

In [the pinned kernel's `sbio.rs`](https://github.com/aurora-silicon/linux/blob/21f7ffcf2e5b3974b3c9cd06e6da4361a9c91667/drivers/soc/apple/sbio.rs#L23),
`admit_enrol()` returns `ENOSPC` for both `live_count >= 3` and
`!host_store_capacity`. Preparation can also return ENOSPC for host persistence
capacity. Both currently produce `enroll-data-full`; neither permits collection.
A distinct explanation needs a separate kernel ABI change, for example `EDQUOT`
for the finger limit while reserving `ENOSPC` for host-store exhaustion, plus
userspace mapping and possibly a new client status. Do not infer the cause by
counting host records or automatically deleting an unrecognized device print.

A later failure saving fprintd's own host record (`store.print_data_save()`
returning `-ENOSPC`) remains `enroll-failed`, as in upstream fprintd. It is a
separate failure after the device enrollment, not the kernel admission failure.
This change does not attempt recovery or deletion in that path.

## Verification

`python3 -m unittest discover -s tests -p test_touchid_capacity.py` applies the
production libfprint patch stack and fprintd Patch1 to licensed upstream function
fixtures, then compiles the actual ioctl mapper, enrollment callback, result
mapper, and CLI callback with fake device/storage APIs. Fixtures retain upstream
copyright and license notices and full-file SHA256 provenance. The RPM's `%check`
also runs the callback harness against the actual fully patched fprintd source.

The fake ioctl returns ENOSPC. All 32 combinations of three existing prints
known/unknown to the host and listing/deletion feature flags must report one
terminal `enroll-data-full`, preserve all device and host records, and make zero
collector, deletion, retry, or save calls. Other-driver positive controls must
still collect an unknown print and retry. Success, general errors, a failed host
save, and the CLI removal instruction are checked too. The collector itself is
modeled in this harness; the no-call assertion is the safety boundary tested.

Hardware acceptance is a separate check: snapshot all three device identities
and host records, attempt a fourth unused finger, require terminal
`enroll-data-full`, compare the full identity set and host records, then verify
the original fingers still match. Include an identity unknown to fprintd where
available. Preserve the before/after evidence and do not remove a print to make
this test pass.

## Draft follow-ups

- Port the paired patches and package dependency guard to alarm-aurora and
  nixos-aurora, including their copies of the earlier ENOSPC suppression patch.
- Split kernel finger-limit and host-store errno values, then give the causes
  distinct diagnostics and agree the D-Bus/client behavior.
- Propose the removal instruction to GNOME Settings upstream, using the
  dedicated three-fingerprint wording only once the cause is distinguishable.
- Perform the three-finger hardware acceptance check separately.
