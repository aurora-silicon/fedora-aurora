#!/usr/bin/env python3
"""Prepare an Aurora-owned KIWI description from a pinned Fedora base."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
PROFILES = {
    "fedora-kde": "Workstation-KDE",
    "fedora-gnome": "Workstation-GNOME",
    "fedora-minimal": "Minimal",
}
# The RPM producer must implement these Fedora-native package contracts.
PACKAGES = {
    "components/boot.xml": ("BootCore", [
        "kernel-aurora", "kernel-aurora-modules-extra", "aura", "uboot-aurora",
    ]),
    "components/base.xml": ("Common", [
        "aurora-release", "aurora-logos", "aurora-platform", "aurora-remix-scripts",
        "aurora-firstboot", "aurora-sep", "libfprint", "mesa-aurora-dri-drivers", "mesa-aurora-vulkan-drivers",
        "aurora-firmware", "avd-fw", "upower", "alsa-ucm-conf-aurora", "aurora-audio", "speakerguardd",
        "speakersafetyd-aurora-profiles",
        # Fedora's SSH server, on every profile; aurora-release presets it off.
        "openssh-server",
    ]),
}
# Quiet by default: the splash (desktops) or a clean console, with failures
# still reported. systemd shows status only when a unit fails or stalls.
QUIET_BOOT = ["quiet", "loglevel=3", "rd.udev.log_level=3", "systemd.show_status=auto"]
ESP_FSCK = '''
# Check the ESP at boot (fsck pass 2), like Fedora's installer.
gawk -i inplace '$2 == "/boot/efi" && $3 == "vfat" { if ($5 == "") $5 = 0; $6 = 2 } { print $0 }' /etc/fstab
'''
REPLACED = {
    "kernel-16k", "kernel-16k-modules-extra", "uboot-images-armv8",
    "asahi-platform-metapackage", "asahi-repos", "fedora-asahi-remix-scripts",
    "alsa-ucm-asahi", "mesa-dri-drivers", "mesa-vulkan-drivers",
    "fedora-release", "fedora-release-workstation", "fedora-release-kde",
}


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def signing_fingerprint(key):
    with tempfile.TemporaryDirectory(prefix="aurora-rpm-key-") as home:
        output = subprocess.check_output([
            "gpg", "--no-options", "--homedir", home, "--batch", "--with-colons",
            "--show-keys", str(Path(key).resolve()),
        ], stderr=subprocess.PIPE, text=True)
    fingerprints = [line.split(":")[9] for line in output.splitlines()
                    if line.startswith("fpr:")]
    if not fingerprints:
        raise ValueError("the repository signing key contains no OpenPGP fingerprint")
    return fingerprints[0]


def write_xml(tree, path):
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def prepare(source, destination, profile, repository_url, key, fingerprint, lock):
    source, destination, key = map(Path, (source, destination, key))
    if profile not in PROFILES:
        raise ValueError("unknown Fedora installation profile")
    if destination.exists():
        raise ValueError("output already exists; use a fresh description directory")
    if source.resolve() in destination.resolve().parents:
        raise ValueError("output must be outside the upstream checkout")
    if git(source, "rev-parse", "HEAD") != lock["commit"]:
        raise ValueError("upstream checkout does not match the pinned commit")
    if git(source, "status", "--porcelain"):
        raise ValueError("upstream checkout is not clean")
    url = urllib.parse.urlsplit(repository_url)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or any(c.isspace() for c in repository_url)):
        raise ValueError("repository URL must be an HTTPS base URL without credentials or query")
    if not key.is_file() or key.is_symlink():
        raise ValueError("repository signing key must be a regular file")
    fingerprint = fingerprint.upper()
    if not re.fullmatch(r"(?:[0-9A-F]{40}|[0-9A-F]{64})", fingerprint):
        raise ValueError("invalid repository signing-key fingerprint")
    if signing_fingerprint(key) != fingerprint:
        raise ValueError("repository signing-key fingerprint does not match")

    destination.mkdir(parents=True)
    for name in ("components", "platforms", "repositories", "root"):
        shutil.copytree(source / name, destination / name)
    for name in ("config.xml", "config.sh", "post_bootstrap.sh", "pre_disk_sync.sh", "COPYING"):
        shutil.copy2(source / name, destination / name)

    # KIWI writes the ESP with fsck pass 0, so nothing ever checks it. Linux
    # never clears a FAT dirty bit by itself, so one unclean shutdown leaves the
    # ESP dirty on every later boot, and macOS then refuses to mount it. Pass 2
    # lets systemd-fsck repair it before the mount, as Fedora's own installer does.
    fstab_script = destination / "root/etc/fstab.script"
    if '$2 == "/boot/efi"' not in fstab_script.read_text():
        raise ValueError("upstream ESP fstab handling changed; review the integration")
    with fstab_script.open("a") as script:
        script.write(ESP_FSCK)

    # No Asahi kernel, bootloader or branding repository can replace Aurora RPMs.
    (destination / "repositories/asahi.xml").unlink()
    for path in destination.rglob("*.xml"):
        tree = ET.parse(path)
        for parent in tree.iter():
            if parent.tag == "type" and parent.get("image") == "oem":
                parent.set("rootfs_label", "AURORA_ROOT")
                arguments = parent.get("kernelcmdline", "").split()
                arguments += [argument for argument in QUIET_BOOT if argument not in arguments]
                parent.set("kernelcmdline", " ".join(arguments))
            if parent.tag == "systemdisk":
                parent.set("name", "aurora")
            for node in list(parent):
                if node.tag == "package" and node.get("name") in REPLACED:
                    parent.remove(node)
                if node.tag == "ignore":
                    name = node.get("name", "")
                    # The shared kernel supports dock and PCIe peripherals.
                    # Upstream's firmware exclusions conflict with that stack.
                    if name in {"generic-release*", "generic-logos*"} or name.endswith("-firmware"):
                        parent.remove(node)
        write_xml(tree, path)

    tree = ET.parse(destination / "config.xml")
    image = tree.getroot()
    image.set("name", "Fedora-Aurora-Remix")
    image.set("displayname", "Fedora Aurora Remix")
    image.find("description/author").text = "Aurora Silicon"
    image.find("description/contact").text = "https://github.com/aurora-silicon/aurora-installer"
    image.find("description/specification").text = "Fedora Aurora Remix for Apple Silicon"
    image.find("preferences/release-version").text = lock["fedora_release"]
    for node in image.findall("include"):
        if node.get("from") == "this://./repositories/asahi.xml":
            node.set("from", "this://./repositories/aurora.xml")
    write_xml(tree, destination / "config.xml")

    for name, (selected_profile, packages) in PACKAGES.items():
        path = destination / name
        tree = ET.parse(path)
        group = ET.SubElement(tree.getroot(), "packages", {
            "type": "image", "profiles": selected_profile,
        })
        for package in packages:
            ET.SubElement(group, "package", {"name": package})
        write_xml(tree, path)

    key_bytes = key.read_bytes()
    key_name = "RPM-GPG-KEY-aurora"
    key_dir = destination / "root/etc/pki/rpm-gpg"
    key_dir.mkdir(parents=True, exist_ok=True)
    (key_dir / key_name).write_bytes(key_bytes)
    # KIWI resolves description-local signing keys before the root filesystem exists.
    (destination / key_name).write_bytes(key_bytes)
    repository = ET.Element("image")
    node = ET.SubElement(repository, "repository", {
        "type": "rpm-md", "alias": "aurora", "sourcetype": "baseurl", "priority": "1",
    })
    origin = ET.SubElement(node, "source", {"path": repository_url.rstrip("/")})
    ET.SubElement(origin, "signing", {"key": (destination.resolve() / key_name).as_uri()})
    write_xml(ET.ElementTree(repository), destination / "repositories/aurora.xml")
    repo_dir = destination / "root/etc/yum.repos.d"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "aurora.repo").write_text(
        "[aurora]\nname=Aurora Silicon for Fedora\n"
        f"baseurl={repository_url.rstrip('/')}\nenabled=1\n"
        f"gpgcheck=1\nrepo_gpgcheck=1\ngpgkey=file:///etc/pki/rpm-gpg/{key_name}\npriority=1\n"
    )
    config = destination / "config.sh"
    text = config.read_text()
    if "kernel-16k-core" not in text:
        raise ValueError("upstream kernel selection changed; review the integration")
    text = text.replace("kernel-16k-core", "kernel-aurora-core")
    if text.count("\nexit 0\n") != 1:
        raise ValueError("upstream image configuration exit changed; review the integration")
    # Check the RPM's preset result inside the assembled image. A build must
    # fail before exporting an image that will omit peripheral admission.
    text = text.replace("\nexit 0\n", '''
# Desktop images create the owner with the desktop's own setup, after Aurora
# has protected the disk on the boot splash.
if [[ -f /usr/lib/systemd/system/plasma-setup.service &&
      ( ! -f /usr/lib/systemd/system/plasma-setup.service.d/aurora-firstboot.conf ||
        ! -f /usr/lib/systemd/system/display-manager.service.d/aurora-plasma-setup.conf ||
        ! -x /usr/libexec/aurora/complete-plasma-setup ||
        "$(systemctl is-enabled plasma-setup.service)" != enabled ) ]]; then
    echo 'Plasma Setup must be enabled and wait for Aurora owner setup in this image' >&2
    exit 1
fi
if [[ -f /usr/lib/systemd/system/gdm.service &&
      ! -f /usr/share/gnome-session/sessions/gnome-initial-setup.session ]]; then
    echo 'GNOME images must create the owner with GNOME Initial Setup' >&2
    exit 1
fi
if [[ -f /usr/lib/systemd/system/plymouth-quit.service &&
      ! -f /usr/lib/systemd/system/plymouth-quit.service.d/aurora-firstboot.conf ]]; then
    echo 'The boot splash must stay up for the first-boot disk-password prompt' >&2
    exit 1
fi

# Reject stale repository images before they can reach installation.
shopt -s nullglob
kernel_configs=(/usr/lib/modules/*/config)
if (( ${#kernel_configs[@]} != 1 )); then
    echo 'Expected exactly one Aurora kernel configuration' >&2
    exit 1
fi
for capability in CONFIG_SECURITY_SELINUX=y CONFIG_SND_SOC_MAX98357A=m; do
    if ! grep -qx "$capability" "${kernel_configs[0]}"; then
        echo "Required Fedora kernel capability missing: $capability" >&2
        exit 1
    fi
done

if [[ "$(systemctl is-enabled aurora-peripherals.service)" != enabled ]]; then
    echo 'Aurora peripheral admission must be enabled in the image' >&2
    exit 1
fi

# Every profile ships the SSH server with remote login off. Re-apply the
# presets now that every package is installed, so install order cannot
# leave it on, and refuse an image that would still start it.
if ! rpm -q openssh-server >/dev/null; then
    echo 'Every Aurora image must ship openssh-server' >&2
    exit 1
fi
systemctl preset sshd.service sshd.socket
for unit in sshd.service sshd.socket; do
    if [[ "$(systemctl is-enabled "$unit" || true)" != disabled ]]; then
        echo "$unit must be off by default in the image" >&2
        exit 1
    fi
done

exit 0
''')
    config.write_text(text)
    receipt = {
        "schema": 1, "distribution": "Fedora Aurora Remix",
        "fedora_release": lock["fedora_release"], "architecture": "aarch64",
        "installation_profile": profile, "kiwi_profile": PROFILES[profile],
        "upstream": lock, "repository_url": repository_url.rstrip("/"),
        "signing_key_fingerprint": fingerprint,
        "signing_key_sha256": hashlib.sha256(key_bytes).hexdigest(),
        "layout": {"kind": "fedora-btrfs-v1", "partitions": ["esp", "boot", "root"],
                   "boot_filesystem": "ext4", "root_filesystem": "btrfs",
                   "root_label": "AURORA_ROOT",
                   "root_subvolume": "root", "home_subvolume": "home",
                   "boot_manager": "grub2", "initramfs": "dracut"},
        "packages": {name: packages for name, (_, packages) in PACKAGES.items()},
        "build_command": ["kiwi-ng", "--target-arch=aarch64", "--type=oem", f"--profile={PROFILES[profile]}",
                          "system", "build", "--description", str(destination.resolve()),
                          "--target-dir", str(destination.resolve().with_name(destination.name + "-image"))],
        "image_built": False,
    }
    (destination / "aurora-image.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES, default="fedora-kde")
    parser.add_argument("--repository-url", required=True)
    parser.add_argument("--signing-key", type=Path, required=True)
    parser.add_argument("--signing-key-fingerprint", required=True)
    args = parser.parse_args()
    try:
        receipt = prepare(args.upstream, args.output, args.profile, args.repository_url,
                          args.signing_key, args.signing_key_fingerprint,
                          json.loads((HERE / "upstream.json").read_text()))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
