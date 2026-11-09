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

With an Apple device: a macOS host routed TCP to this Mac over AWDL at 144-191 Mbit/s. Set Apple devices to **Everyone** (on an iPhone: Settings > General > AirDrop). Without an Apple-issued identity, this Mac uses a self-signed one, and Contacts Only devices refuse it. The first send creates `~/.omdrop/keys/*.self-signed.pem`.

## Speed and the main Wi-Fi link

When `/etc/omdrop/peer-chan` is not set, `awdl-up` puts AWDL's availability windows on the 5 GHz channel the Wi-Fi link already uses (36-48 or 149-161), with the `full` slot shape, and advertises that sequence. This is what macOS does: its idle AWDL schedule stays on the infra channel except for channel 6 in one slot. Measured 2026-11-08 on an M2 MacBook Air and an M1 Pro MacBook Pro with the Wi-Fi link on channel 149:

| AWDL schedule | Main Wi-Fi link | AWDL between the two Macs |
|---|---|---|
| none | 171 Mbit/s | none |
| upstream default (peer 44, dense) | 142 Mbit/s | 1.5-7 Mbit/s, 40-50 % ping loss |
| infra channel 149, full | 263 Mbit/s | 188 Mbit/s, 0 % ping loss |

A 100 MB AirDrop took 8 s on the 149 schedule. On a 2.4 GHz or DFS link, the upstream default stays. To choose the channel yourself:

```bash
echo 44 | sudo tee /etc/omdrop/peer-chan     # and optionally: echo dense | sudo tee /etc/omdrop/chan-shape
sudo /usr/libexec/omdrop/awdl-up --reload   # reloads brcmfmac: Wi-Fi drops for a few seconds
```

The schedule is set when `awdl0` is created. If the Mac joins a network on another channel later, run `awdl-up --reload`, or recreate `awdl0`, to follow it.

## Aurora changes from upstream
- The helpers are in `/usr/libexec/omdrop`, not `/usr/lib/omdrop`.
- `awdl-up` accepts Fedora's per-network cloned Wi-Fi MAC (`wifi.cloned-mac-address=stable-ssid`) once the Mac is connected. Upstream refuses to create `awdl0` while a cloned MAC is in use.
- No DKMS module and no `brcmfmac` debug setting: kernel-aurora's driver already has AWDL.
- Each window sets AWDL's 5 GHz social channel (`awdl_osoc_chan`) to 149, or to the value in `/etc/omdrop/osoc-chan`. Left at the firmware default, macOS hears this Mac only on 2.4 GHz and won't route to it. Its log shows `Not Routable. Peer discovered(on 2.4GHz only)`.
- `awdl-warmup.service` is installed disabled. Upstream enables it.
- With no `/etc/omdrop/peer-chan`, the AWDL channel follows the Wi-Fi link (see above). Upstream always uses 44.
