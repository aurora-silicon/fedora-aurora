#!/bin/bash
# Run only through the owner's approved controller/session workflow.
set -euo pipefail
D=$(cd -- "$(dirname -- "$0")" && pwd)
source "$D/machine.env"
if [[ ${KIT_BLOCKED:-yes} != no ]]; then cat "$D/BLOCKED.txt" >&2; exit 78; fi
if [[ ${1:-} != --apply ]]; then
  printf 'Owner installation plan (%s, Fedora %s):\n' "$MACHINE" "$FEDORA"
  cat "$D/INSTALL-RPMS.txt"
  printf 'After controller authorization, pre-verification and lock review: sudo bash install.sh --apply\n'
  exit 0
fi
[[ $EUID == 0 && $(uname -m) == aarch64 ]] || { echo 'Requires root on AArch64' >&2; exit 2; }
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
# verify.sh pre records the active local owner's session, unchanged shell,
# audio guard, boot and journal cursor. It is run separately under policy.
[[ -f state/pre-boot && $(cat /proc/sys/kernel/random/boot_id) == "$(cat state/pre-boot)" ]] || {
  echo 'Missing current-boot pre-verification; read README.md' >&2; exit 2;
}
[[ ! -e state/install-started ]] || { echo 'Existing attempt retained; use a fresh kit' >&2; exit 2; }
# No plugin or lock bypass: configured DNF trust and versionlock policy applies.
# Keep all evidence, including a refused transaction.
rpm -qa --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}.rpm\n' | sort > state/before-rpm-filenames
# Every installed package this migration may replace needs an exact rollback RPM.
payload_tags=$(rpm --querytags)
if grep -Fx PAYLOADSHA256 <<< "$payload_tags" >/dev/null; then
  payload_tag=PAYLOADSHA256
elif grep -Fx PAYLOADDIGEST <<< "$payload_tags" >/dev/null; then
  payload_tag=PAYLOADDIGEST
else
  echo 'RPM has no supported payload identity query tag' >&2; exit 78
fi
format="%{NAME} %{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH} %{${payload_tag}}"
: > state/rollback-rpms
while IFS= read -r name; do
  if filename=$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}.rpm' "$name" 2>/dev/null); then
    path=$(find "$D/rollback/rpms" -type f -name "$filename" -print -quit)
    [[ -n $path ]] || { echo "Missing exact rollback: $filename" >&2; exit 78; }
    # Filenames omit Epoch and can be reused by local rebuilds. Match the
    # installed header and payload identity as well as NVR/architecture.
    installed=$(rpm -q --qf "$format" "$name")
    staged=$(rpm -qp --qf "$format" "$path")
    digest=$(rpm -q --qf "%{${payload_tag}}" "$name")
    [[ $digest =~ ^[0-9a-f]+$ && $installed == "$staged" ]] || {
      echo "Rollback RPM does not match the installed header/payload: $filename" >&2; exit 78;
    }
    printf '%s\n' "$path" >> state/rollback-rpms
  fi
done < "$D/AFFECTED-NAMES.txt"
[[ -s state/rollback-rpms ]] || { echo 'Unsupported empty baseline' >&2; exit 78; }
# Explicit list; optional FEX/devel/OpenCL are selected only if already installed.
mapfile -t rpms < "$D/INSTALL-RPMS.txt"
for item in devel libOpenCL libOpenCL-devel; do
  case $item in
    devel) names=(mesa-libEGL-devel mesa-libGL-devel mesa-libgbm-devel mesa-aurora-devel) ;;
    libOpenCL) names=(mesa-libOpenCL mesa-aurora-libOpenCL) ;;
    libOpenCL-devel) names=(mesa-libOpenCL-devel mesa-aurora-libOpenCL-devel) ;;
  esac
  found=no
  for name in "${names[@]}"; do if rpm -q "$name" >/dev/null 2>&1; then found=yes; fi; done
  if [[ $found == yes ]]; then
    rpms+=("./optional-rpms/mesa-aurora-$item-26.3.0-11.fc44.aurora.aarch64.rpm")
  fi
done
if rpm -q mesa-aurora-fex-guest >/dev/null 2>&1; then
  rpms+=(./optional-rpms/mesa-aurora-fex-guest-26.3.0-11.fc44.aurora.noarch.rpm)
fi
printf '%s\n' "${rpms[@]}" > state/install-rpms
# DNF performs a transaction test before committing; no erasing/skip flags.
touch state/install-started
dnf --setopt=install_weak_deps=False install "${rpms[@]}" 2>&1 | tee state/install.log
rpm -qa --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}.rpm\n' | sort > state/after-rpm-filenames
touch state/install-completed
printf 'Transaction complete. Run the approved verify.sh post check; keep the rollback evidence.\n'
