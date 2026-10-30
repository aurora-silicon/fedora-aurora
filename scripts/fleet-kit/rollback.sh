#!/bin/bash
# Restore only the packages captured immediately before this kit's transaction.
set -euo pipefail
D=$(cd -- "$(dirname -- "$0")" && pwd)
source "$D/machine.env"
if [[ ${KIT_BLOCKED:-yes} != no ]]; then cat "$D/BLOCKED.txt" >&2; exit 78; fi
if [[ ${1:-} != --apply ]]; then
  echo 'Owner rollback plan: restore state/rollback-rpms in one DNF5 transaction.'
  echo 'Run through the approved controller/session workflow: sudo bash rollback.sh --apply'
  exit 0
fi
[[ $EUID == 0 && $(uname -m) == aarch64 ]] || exit 2
source /etc/os-release
[[ $ID == fedora && $VERSION_ID == "$FEDORA" ]] || exit 2
tr '\0' '\n' < /proc/device-tree/compatible | grep -Fxq "$BOARD"
# Re-check the live owner session against the pre-check evidence.
sid=$(loginctl show-seat seat0 -p ActiveSession --value)
[[ -n $sid && $(loginctl show-session "$sid" -p Remote --value) == no && $(loginctl show-session "$sid" -p Active --value) == yes ]] || exit 2
uid=$(loginctl show-session "$sid" -p User --value)
[[ $uid =~ ^[0-9]+$ && $uid -gt 0 ]] || exit 2
[[ -f $D/state/pre-shell && $(pgrep -u "$uid" -x gnome-shell | sort) == "$(cat "$D/state/pre-shell")" ]] || exit 2
[[ -f $D/state/pre-sg && $(systemctl show speakerguardd -p MainPID -p NRestarts -p ActiveEnterTimestampMonotonic) == "$(cat "$D/state/pre-sg")" ]] || exit 2
systemctl is-active --quiet speakerguardd
cd "$D"
sha256sum --check SHA256SUMS
[[ -f state/install-completed && -s state/rollback-rpms && ! -e state/rollback-started ]] || {
  echo 'Missing successful installation record, or existing rollback attempt retained' >&2; exit 78;
}
mapfile -t old < state/rollback-rpms
remove=()
# Different names require an atomic rename reversal; same-name packages use
# install's --allow-downgrade. Never run a separate erase transaction.
for name in mesa-aurora-dri-drivers mesa-aurora-vulkan-drivers mesa-aurora-vulkan-lavapipe mesa-aurora-devel mesa-aurora-libOpenCL mesa-aurora-libOpenCL-devel aurora-flatpak-gl; do
  if rpm -q "$name" >/dev/null 2>&1 && ! grep -q "^$name-[0-9]" state/before-rpm-filenames; then
    remove+=("$name")
  fi
done
args=(--setopt=install_weak_deps=False do)
if (( ${#remove[@]} )); then args+=(--action=remove "${remove[@]}"); fi
args+=(--action=install --allow-downgrade "${old[@]}")
# Old incoming RPMs predate the upgrade fix. Unmount explicitly for rollback,
# including when the current release knows how to handle forward upgrades.
restore_fex() {
  rc=$?
  if [[ -e state/fex-rollback-restart-needed ]]; then
    if systemctl start aurora-fex-mesa.service; then
      rm state/fex-rollback-restart-needed
    else
      echo 'FEX overlay remount failed; recovery marker retained' >&2
      [[ $rc != 0 ]] || rc=1
    fi
  fi
  exit "$rc"
}
trap restore_fex EXIT
if rpm -q mesa-aurora-fex-guest >/dev/null 2>&1 && systemctl -q is-active aurora-fex-mesa.service; then
  systemctl stop aurora-fex-mesa.service
  touch state/fex-rollback-restart-needed
fi
touch state/rollback-started
dnf "${args[@]}" 2>&1 | tee state/rollback.log
# Exact old package versions must all be back, including renamed devel/OpenCL.
for path in "${old[@]}"; do
  expected=$(rpm -qp --qf '%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}' "$path")
  name=$(rpm -qp --qf '%{NAME}' "$path")
  [[ $(rpm -q --qf '%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}' "$name") == "$expected" ]]
done
touch state/rollback-completed
echo 'Package rollback complete. Restore reviewed versionlocks from the pre-check backup and verify old driverInfo.'
