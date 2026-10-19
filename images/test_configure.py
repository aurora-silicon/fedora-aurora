#!/usr/bin/env python3
"""Exercise image preparation without building or installing an operating system."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location("configure", Path(__file__).with_name("configure.py"))
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


class ConfigureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="aurora-fedora-test-")
        cls.root = Path(cls.temporary.name)
        cls.source = cls.root / "upstream"
        cls.source.mkdir()
        for name in ("components", "platforms", "repositories", "root"):
            (cls.source / name).mkdir()
        (cls.source / "config.xml").write_text('''<image name="Fedora-Asahi-Remix">
          <description><author>Upstream</author><contact>upstream@example.org</contact><specification>Upstream</specification></description>
          <preferences><release-version>44</release-version><rpm-check-signatures>true</rpm-check-signatures></preferences>
          <include from="this://./repositories/asahi.xml"/></image>''')
        for path, (profile, _) in configure.PACKAGES.items():
            (cls.source / path).write_text(
                f'<image><packages type="image" profiles="{profile}"><package name="kernel-16k"/>'
                '<package name="fedora-release-kde"/><package name="mesa-dri-drivers"/></packages></image>')
        (cls.source / "repositories/asahi.xml").write_text("<image/>")
        for name in ("config.sh", "post_bootstrap.sh", "pre_disk_sync.sh"):
            (cls.source / name).write_text("#!/bin/bash\nset -euo pipefail\n# kernel-16k-core\nexit 0\n")
        (cls.source / "COPYING").write_text("upstream license fixture\n")
        subprocess.run(["git", "init", "-q", str(cls.source)], check=True)
        subprocess.run(["git", "-C", str(cls.source), "add", "."], check=True)
        subprocess.run(["git", "-C", str(cls.source), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.org", "commit", "-qm", "fixture"], check=True)
        cls.lock = {"commit": configure.git(cls.source, "rev-parse", "HEAD"), "fedora_release": "44"}
        cls.home = cls.root / "gpg"
        cls.home.mkdir(mode=0o700)
        subprocess.run(["gpg", "--no-options", "--homedir", str(cls.home), "--batch",
                        "--pinentry-mode", "loopback", "--passphrase", "", "--quick-generate-key",
                        "Aurora fixture <fixture@example.org>", "ed25519", "sign", "0"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.key = cls.root / "key.asc"
        cls.key.write_bytes(subprocess.check_output([
            "gpg", "--no-options", "--homedir", str(cls.home), "--armor", "--export",
        ]))
        cls.fingerprint = configure.signing_fingerprint(cls.key)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def prepare(self, output, **kwargs):
        args = dict(source=self.source, destination=output, profile="fedora-kde",
                    repository_url="https://packages.example.org/fedora/44/aarch64",
                    key=self.key, fingerprint=self.fingerprint, lock=self.lock)
        args.update(kwargs)
        return configure.prepare(**args)

    def test_all_profiles_keep_fedora_layout_and_aurora_packages(self):
        for profile, kiwi in configure.PROFILES.items():
            with self.subTest(profile=profile):
                out = self.root / profile
                receipt = self.prepare(out, profile=profile)
                self.assertEqual(receipt["kiwi_profile"], kiwi)
                self.assertFalse(receipt["image_built"])
                self.assertIn("--target-arch=aarch64", receipt["build_command"])
                self.assertEqual(receipt["layout"]["root_subvolume"], "root")
                self.assertEqual(receipt["layout"]["boot_manager"], "grub2")
                image = ET.parse(out / "config.xml").getroot()
                self.assertEqual(image.get("name"), "Fedora-Aurora-Remix")
                self.assertEqual(image.find("preferences/rpm-check-signatures").text, "true")
                names = {n.get("name") for p in out.rglob("*.xml")
                         for n in ET.parse(p).getroot().iter("package")}
                self.assertFalse(configure.REPLACED & names)
                self.assertIn("kernel-aurora", names)
                self.assertIn("mesa-aurora-vulkan-drivers", names)
                self.assertFalse((out / "repositories/asahi.xml").exists())
                self.assertIn("repo_gpgcheck=1", (out / "root/etc/yum.repos.d/aurora.repo").read_text())
                self.assertEqual((out / "root/etc/pki/rpm-gpg/RPM-GPG-KEY-aurora").read_bytes(), self.key.read_bytes())
                self.assertEqual((out / "COPYING").read_text(), "upstream license fixture\n")
                self.assertEqual(json.loads((out / "aurora-image.json").read_text()), receipt)
        self.assertEqual(configure.git(self.source, "status", "--porcelain"), "")

    def test_rejects_wrong_source_key_profile_and_unsafe_repository(self):
        cases = [dict(lock={**self.lock, "commit": "0" * 40}),
                 dict(fingerprint="0" * 40), dict(profile="not-fedora"),
                 dict(repository_url="http://packages.example.org"),
                 dict(repository_url="https://user:secret@packages.example.org"),
                 dict(repository_url="https://packages.example.org/?token=secret")]
        for index, kwargs in enumerate(cases):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.prepare(self.root / f"rejected-{index}", **kwargs)
            self.assertFalse((self.root / f"rejected-{index}").exists())

    def test_does_not_overwrite_an_existing_description(self):
        destination = self.root / "existing"
        destination.mkdir()
        (destination / "keep").write_text("preserve")
        with self.assertRaises(ValueError):
            self.prepare(destination)
        self.assertEqual((destination / "keep").read_text(), "preserve")

    def test_image_configuration_rejects_inactive_peripheral_presets(self):
        output = self.root / "peripheral-preset"
        self.prepare(output)
        image_root = self.root / "peripheral-image-root"
        config = output / "config.sh"
        config.write_text(config.read_text().replace("/usr/lib/systemd/system", str(image_root / "usr/lib/systemd/system"))
                          .replace("/usr/libexec/aurora", str(image_root / "usr/libexec/aurora"))
                          .replace("/usr/lib/modules/", str(image_root / "usr/lib/modules") + "/"))
        kernel = image_root / "usr/lib/modules/fixture/config"
        kernel.parent.mkdir(parents=True)
        kernel.write_text("CONFIG_SECURITY_SELINUX=y\nCONFIG_SND_SOC_MAX98357A=m\n")
        commands = self.root / "mock-commands"
        commands.mkdir()
        systemctl = commands / "systemctl"
        systemctl.write_text('#!/bin/bash\nprintf "%s\\n" "$AURORA_TEST_UNIT_STATE"\n')
        systemctl.chmod(0o755)
        for state in ("enabled", "disabled", "masked", "static"):
            with self.subTest(state=state):
                result = subprocess.run(["bash", str(output / "config.sh")],
                                        env={**os.environ, "PATH": str(commands) + ":" + os.environ["PATH"],
                                             "AURORA_TEST_UNIT_STATE": state},
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(result.returncode == 0, state == "enabled")

    def test_kde_image_requires_both_setup_ordering_and_login_cleanup(self):
        output = self.root / "plasma-setup-contract"
        self.prepare(output)
        image = self.root / "plasma-image-root"
        units = image / "usr/lib/systemd/system"
        units.mkdir(parents=True)
        config = output / "config.sh"
        config.write_text(config.read_text().replace("/usr/lib/systemd/system", str(units))
                          .replace("/usr/libexec/aurora", str(image / "usr/libexec/aurora"))
                          .replace("/usr/lib/modules/", str(image / "usr/lib/modules") + "/"))
        kernel = image / "usr/lib/modules/fixture/config"
        kernel.parent.mkdir(parents=True)
        kernel.write_text("CONFIG_SECURITY_SELINUX=y\nCONFIG_SND_SOC_MAX98357A=m\n")
        commands = self.root / "plasma-commands"
        commands.mkdir()
        command = commands / "systemctl"
        command.write_text("#!/bin/sh\nprintf 'enabled\\n'\n")
        command.chmod(0o755)
        env = {**os.environ, "PATH": str(commands) + ":" + os.environ["PATH"]}

        def accepted():
            return subprocess.run(["bash", str(config)], env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE).returncode == 0

        self.assertTrue(accepted())  # Minimal images have no Plasma Setup.
        (units / "plasma-setup.service").touch()
        self.assertFalse(accepted())
        ordering = units / "plasma-setup.service.d/aurora-firstboot.conf"
        ordering.parent.mkdir()
        ordering.touch()
        self.assertFalse(accepted())  # The earlier ordering-only RPM is insufficient.
        cleanup = units / "display-manager.service.d/aurora-plasma-setup.conf"
        cleanup.parent.mkdir()
        cleanup.touch()
        self.assertFalse(accepted())
        helper = image / "usr/libexec/aurora/complete-plasma-setup"
        helper.parent.mkdir(parents=True)
        helper.touch()
        self.assertFalse(accepted())
        helper.chmod(0o755)
        self.assertTrue(accepted())

    def test_image_rejects_a_stale_kernel_before_export(self):
        output = self.root / "kernel-gate"
        self.prepare(output)
        image = self.root / "kernel-image-root"
        config = output / "config.sh"
        config.write_text(config.read_text().replace("/usr/lib/systemd/system", str(image / "usr/lib/systemd/system"))
                          .replace("/usr/lib/modules/", str(image / "usr/lib/modules") + "/"))
        kernel = image / "usr/lib/modules/fixture/config"
        kernel.parent.mkdir(parents=True)
        commands = self.root / "kernel-commands"
        commands.mkdir()
        systemctl = commands / "systemctl"
        systemctl.write_text("#!/bin/sh\nprintf 'enabled\n'\n")
        systemctl.chmod(0o755)
        env = {**os.environ, "PATH": str(commands) + ":" + os.environ["PATH"]}
        def accepted():
            return subprocess.run(["bash", str(config)], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0
        self.assertFalse(accepted())
        kernel.write_text("# CONFIG_SECURITY_SELINUX is not set\n# CONFIG_SND_SOC_MAX98357A is not set\n")
        self.assertFalse(accepted())
        kernel.write_text("CONFIG_SECURITY_SELINUX=y\n")
        self.assertFalse(accepted())
        kernel.write_text("CONFIG_SECURITY_SELINUX=y\nCONFIG_SND_SOC_MAX98357A=m\n")
        self.assertTrue(accepted())
        other = image / "usr/lib/modules/other/config"
        other.parent.mkdir()
        other.write_bytes(kernel.read_bytes())
        self.assertFalse(accepted())

    def test_output_cannot_recurse_into_the_upstream_checkout(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            self.prepare(self.source / "generated")
        self.assertFalse((self.source / "generated").exists())


if __name__ == "__main__":
    unittest.main()
