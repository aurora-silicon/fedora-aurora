# Isolated single-board test RPMs

The regular recipe and fleet source pin stay unchanged. To build a Plan A
snapshot from a clean public speakerguardd tree that includes
`packaging/plan-a/gate.py` and the sleep fixes, supply these rpmbuild macros:

```
--define 'commit FULL_SOURCE_SHA' --define 'snapdate YYYYMMDD' \
--define 'plan_a_board j316s'
```

Provide the matching `speakerguardd-v2-FULL_SOURCE_SHA.tar.gz` in SOURCES,
with the usual `speakerguardd-FULL_SOURCE_SHA/` archive prefix. Build in the
board's Fedora aarch64 container with the existing build requirements and
Aurora Silicon vendor. Allowed boards are j616s, j316s and j413; the upstream
generator rejects other names. The release is
`0.13.DATE.1.planA.BOARD.gitSHA.fcNN`, separate from fleet releases. The numeric serial sorts above the same-date
fleet snapshot; use `--define 'plan_a_serial 2'` (then 3, etc.) for respins
so ordering does not depend on the source SHA. See the
[RPM version rules](https://rpm.org/docs/6.1.x/man/rpm-version.7).

The j413 macro automatically enables `sgv2-core/lowflow-conservative` for
both the workspace build (compiler and plugin), tests and blob-info. The
other boards use the default flavor. The source default gate remains empty;
only the installed gate selects one board. The RPM includes blob-info under
`/usr/libexec/speakerguardd-v2` for parameter-free summary verification.

These are test packages, pending the owner's board qualification. A snapshot
built before a DSP correction must be rebuilt at the passing revision. No
per-machine tuning belongs in source archives, RPMs or kits.
