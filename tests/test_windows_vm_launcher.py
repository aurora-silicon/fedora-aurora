"""Contract tests for the fail-closed Windows Neptune launcher."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "packages/aurora-windows-vm/aurora-windows-vm"


class WindowsVMLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.disk = root / "windows.raw"
        self.code = root / "code.fd"
        self.vars = root / "vars.fd"
        for path in (self.disk, self.code, self.vars):
            path.write_bytes(b"test")
        self.driver = root / "driver"
        self.driver.mkdir()
        for name in (
            "viogpu3d.sys", "viogpu3d.inf", "viogpu3d.cat",
            "neptune_umd.dll", "vulkan_virtio.dll", "virtio_icd.json",
        ):
            (self.driver / name).write_bytes(b"test")
        (self.driver / "driver-signature.txt").write_text(
            "Authenticode=valid\nArchitecture=ARM64\n", encoding="ascii"
        )
        self.bin = root / "bin"
        self.bin.mkdir()
        self.qemu = self.bin / "qemu"
        self.qemu.write_text(
            "#!/bin/sh\n"
            "case \"$*\" in *virtio-gpu-gl-pci,help*) "
            "if [ \"${FAKE_NEPTUNE:-0}\" = 1 ]; then echo 'neptune blob hostmem'; fi;; esac\n"
            "case \"$*\" in *virtio-gpu-gl-pci,hostmem=*) "
            "if [ -n \"${CAPTURE_ENV:-}\" ]; then printf '%s' \"${LD_LIBRARY_PATH:-}\" > \"$CAPTURE_ENV\"; fi;; esac\n",
            encoding="ascii",
        )
        self.qemu.chmod(0o755)
        # The test package contains placeholder bytes; the launcher still
        # performs its ARM64 check. Replace `file` in PATH with a deterministic
        # probe while testing the launch contract.
        file_probe = self.bin / "file"
        file_probe.write_text("#!/bin/sh\necho ARM64\n", encoding="ascii")
        file_probe.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_launcher(self, *extra, neptune=True, backend=True, host_prefix=None, dry_run=True):
        env = os.environ.copy()
        env["PATH"] = f"{self.bin}:{env['PATH']}"
        env["FAKE_NEPTUNE"] = "1" if neptune else "0"
        if backend:
            for name in ("NPT_D3D11_LIBRARY_PATH", "NPT_DXGI_LIBRARY_PATH", "NPT_D3D12_LIBRARY_PATH"):
                path = Path(self.tmp.name) / name
                path.write_bytes(b"backend")
                env[name] = str(path)
        if host_prefix is not None:
            env.pop("NPT_D3D11_LIBRARY_PATH", None)
            env.pop("NPT_DXGI_LIBRARY_PATH", None)
            env.pop("NPT_D3D12_LIBRARY_PATH", None)
        cmd = [
            str(LAUNCHER), "--disk", str(self.disk),
            "--uefi-code", str(self.code), "--uefi-vars", str(self.vars),
            "--qemu", str(self.qemu), "--guest-driver-dir", str(self.driver),
            *( (["--dry-run"] if dry_run else []) ),
            *( (["--host-prefix", str(host_prefix)] if host_prefix is not None else []) ), *extra,
        ]
        return subprocess.run(cmd, env=env, text=True, capture_output=True)

    def test_accelerated_command_has_neptune_device(self):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("virtio-gpu-gl-pci,hostmem=4G,blob=on,neptune=on", result.stdout.replace("\\,", ","))
        # QEMU requires an integer for -smp; the launcher must not emit the
        # tempting but invalid `-smp host` spelling.
        command = result.stdout.replace("\\,", ",").split()
        smp = command.index("-smp")
        self.assertRegex(command[smp + 1], r"^[1-9][0-9]*$")

    def test_invalid_cpu_count_is_rejected(self):
        result = self.run_launcher()
        # run_launcher inherits the host default; override it explicitly for
        # the validation path.
        env = os.environ.copy()
        env["PATH"] = f"{self.bin}:{env['PATH']}"
        env["FAKE_NEPTUNE"] = "1"
        for name in ("NPT_D3D11_LIBRARY_PATH", "NPT_DXGI_LIBRARY_PATH", "NPT_D3D12_LIBRARY_PATH"):
            path = Path(self.tmp.name) / name
            path.write_bytes(b"backend")
            env[name] = str(path)
        cmd = [
            str(LAUNCHER), "--disk", str(self.disk),
            "--uefi-code", str(self.code), "--uefi-vars", str(self.vars),
            "--qemu", str(self.qemu), "--guest-driver-dir", str(self.driver),
            "--cpus", "host", "--dry-run",
        ]
        invalid = subprocess.run(cmd, env=env, text=True, capture_output=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("positive integer", invalid.stderr)

    def test_missing_neptune_fails_closed(self):
        result = self.run_launcher(neptune=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no Neptune", result.stderr)

    def test_missing_signed_driver_fails_closed(self):
        (self.driver / "driver-signature.txt").unlink()
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("package is incomplete", result.stderr)

    def test_missing_backend_fails_closed(self):
        result = self.run_launcher(backend=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required for Linux/Vulkan Neptune", result.stderr)

    def test_host_prefix_supplies_backend_libraries(self):
        prefix = Path(self.tmp.name) / "prefix"
        lib = prefix / "lib"
        lib.mkdir(parents=True)
        for name in ("libd3d11.so", "libdxgi.so", "libvkd3d-proton-d3d12.so"):
            (lib / name).write_bytes(b"backend")
        result = self.run_launcher(backend=False, host_prefix=prefix)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("virtio-gpu-gl-pci,hostmem=4G,blob=on,neptune=on", result.stdout.replace("\\,", ","))

    def test_host_prefix_is_added_to_qemu_loader_path(self):
        prefix = Path(self.tmp.name) / "prefix"
        lib = prefix / "lib"
        lib.mkdir(parents=True)
        for name in ("libd3d11.so", "libdxgi.so", "libvkd3d-proton-d3d12.so"):
            (lib / name).write_bytes(b"backend")
        capture = Path(self.tmp.name) / "loader-path"
        env = os.environ.copy()
        env["PATH"] = f"{self.bin}:{env['PATH']}"
        env["FAKE_NEPTUNE"] = "1"
        env["CAPTURE_ENV"] = str(capture)
        cmd = [
            str(LAUNCHER), "--disk", str(self.disk),
            "--uefi-code", str(self.code), "--uefi-vars", str(self.vars),
            "--qemu", str(self.qemu), "--guest-driver-dir", str(self.driver),
            "--host-prefix", str(prefix),
        ]
        result = subprocess.run(cmd, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(capture.read_text(), f"{lib}:{os.environ.get('LD_LIBRARY_PATH', '')}".rstrip(":"))


if __name__ == "__main__":
    unittest.main()
