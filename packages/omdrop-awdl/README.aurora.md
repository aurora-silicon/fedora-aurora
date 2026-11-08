# AirDrop over AWDL on Aurora

On Apple Silicon Macs, the Broadcom Wi-Fi firmware implements AWDL, the peer-to-peer Wi-Fi link that AirDrop runs over. kernel-aurora's `brcmfmac` exposes it as `awdl0`. This package adds the userspace for it: the omdrop-awdl helpers (netmojo-systems/omdrop-awdl) and the omdrop-plugin receiver.

Works on Macs with BCM4378, BCM4387 or BCM4388 Wi-Fi. Run `lspci -nn | grep 14e4:44` to check. The Neo's MediaTek Wi-Fi has no AWDL.

Nothing runs after installing. Every step below is opt-in.

## Use it

```bash
# 1. Create awdl0. It stays idle until a window opens. To create it at every boot instead:
#    sudo systemctl enable --now awdl0.service
sudo /usr/libexec/omdrop/awdl-up

# 2. Be discoverable for ten minutes. A desktop session needs no password.
pkexec /usr/libexec/omdrop/omdrop-discoverable start 600

# 3. Receive into ~/Downloads while the window is open.
systemctl --user start airdrop-receiver.service

# 4. Send.
/usr/libexec/omdrop/send-to-peer --list --names                  # who is in range
/usr/libexec/omdrop/send-to-peer --mac <peer MAC> FILE...         # a Mac or an iPhone
/usr/libexec/omdrop/send-to-peer --mac <peer MAC> --port 8771 FILE   # another Linux Mac

# 5. Done.
systemctl --user stop airdrop-receiver.service
pkexec /usr/libexec/omdrop/omdrop-discoverable stop
```

Set Apple devices to **Everyone** (on an iPhone: Settings > General > AirDrop). Without an Apple-issued identity, this Mac uses a self-signed one, and Contacts Only devices refuse it. The first send creates `~/.omdrop/keys/*.self-signed.pem`.

## Speed

The default AWDL schedule (peer channel 44, `dense`) carried 1.5 to 7 Mbit/s between two Linux Macs whose Wi-Fi was on channel 149. Setting the peer channel to the Wi-Fi channel brought it to 188 Mbit/s with no ping loss:

```bash
echo 149 | sudo tee /etc/omdrop/peer-chan
echo full | sudo tee /etc/omdrop/chan-shape
sudo /usr/libexec/omdrop/awdl-up --reload   # reloads brcmfmac: Wi-Fi drops for a few seconds
```

Measured 2026-11-08 on an M2 MacBook Air and an M1 Pro MacBook Pro: a 100 MB AirDrop took 8 s.

## Aurora changes from upstream
- The helpers are in `/usr/libexec/omdrop`, not `/usr/lib/omdrop`.
- `awdl-up` accepts Fedora's per-network cloned Wi-Fi MAC (`wifi.cloned-mac-address=stable-ssid`) once the Mac is connected. Upstream refuses to create `awdl0` while a cloned MAC is in use.
- No DKMS module and no `brcmfmac` debug setting: kernel-aurora's driver already has AWDL.
- `awdl-warmup.service` is installed disabled. Upstream enables it.
