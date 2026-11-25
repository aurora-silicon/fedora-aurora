# aurora-m5-platform-config

This package provides a logind lid policy when Linux selects deep sleep.
It uses the active mode in `/sys/power/mem_sleep`. Linux registers the
deep mode once the platform sleep driver admits it. The policy requires
`[deep]`, so kernels that select s2idle keep their normal lid settings
even if they also advertise a testable deep mode.

Logind handles lid-close events from a registered lid switch. On battery,
AC or a dock, a lid close then asks logind to suspend. GNOME and Plasma can
handle the lid through their own policies.

The package leaves the Linux sleep mode and RTC wake alarms to their
owners. Current T6050 sleep kernels accept lid and keyboard wake without
an armed alarm (Linux commit `26bf5f527f1e`). Older development kernels that
require an alarm may need an explicit timed wake for testing.

An override at `/etc/systemd/logind.conf.d/90-aurora-m5-lid.conf` takes
precedence. Masking `aurora-m5-sleep-policy.service` keeps the normal lid
policy at the next boot.

## Earlier J714s test observations (2026-11-20)

- A sleep entered right after a USB-C event on a Dell monitor's port can hang before the commit,
  in about 1 in 10 such sleeps; the watchdog restarts the Mac about 2 minutes later.
- The Dell monitor's SuperSpeed hub can be missing after about 15 % of boots. It comes back after
  the first sleep.
- A stray Wi-Fi/Bluetooth wake right after the sleep's entry is taken as a dark wake: user space
  stays frozen and the Mac sleeps again.
