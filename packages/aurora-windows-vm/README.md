# Aurora Windows GPU VM

`aurora-windows-vm` launches a Windows ARM64 guest with UTM's Linux Neptune
backend. Neptune is the virtio protocol used by UTM's Windows WDDM driver to
forward D3D11/D3D12 work to the host Vulkan D3D12 backend. A plain
`virtio-gpu-pci` device is only a 2D framebuffer and is deliberately rejected
by the accelerated mode.

The guest must have UTM's `viogpu3d` WDDM driver installed. The driver package
contains `neptune_umd.dll` and the Venus ICD; build instructions are in the
upstream `osy/kvm-guest-drivers-windows` `neptune` branch
(`viogpu/viogpu3d/BUILDING.md`). The source branch currently resolves to
`ed821008215ded87d2d03495240d5aad6d8e42ba`; record the exact source revision
when producing the signed package.
The package also provides `fetch-guest-driver.sh`, pinned to the signed ARM64X
`v0.5` release. It verifies the archive SHA-256 and stages the package; run
`verify-guest-driver.ps1` on Windows to verify its catalog and create the
`driver-signature.txt` record required by the launcher.

The Linux host needs matching UTM components:

* `utmapp/qemu` `utm-edition`, with `virtio-gpu-gl-pci` and the `neptune` property.
* `utmapp/virglrenderer` `staging/neptune-linux`, configured with
  `-Dneptune=true -Dvenus=true`.
* the UTM DXVK fork (`libd3d11.so`/`libdxvk_d3d11.so`,
  `libdxgi.so`/`libdxvk_dxgi.so`) and vkd3d-proton exposing
  `libvkd3d-proton-d3d12.so`; these backends use the host Vulkan 1.3
  implementation. Set `NPT_D3D11_LIBRARY_PATH`, `NPT_DXGI_LIBRARY_PATH`, and
  `NPT_D3D12_LIBRARY_PATH` when they are not in `/usr/lib` or `/usr/lib64`.

`build-neptune-stack.sh` pins and builds the UTM DXVK native headless ABI
automatically when `dxvk-dxgi.pc` is absent, builds the pinned native
vkd3d-proton D3D12 backend, then builds the pinned virglrenderer and QEMU.
The vkd3d build requires `widl` (from Wine) and `glslangValidator`; a
standalone binary may be supplied with `AURORA_WIDL_PATH`, or discovered from
`AURORA_WINE_SOURCE/tools/widl/widl` for an offline build guest. The build applies the reviewed
`0001-neptune-directx-native-abi.patch` because the pinned virglrenderer
commit predates DXVK's migration to the directx-native shared-resource ABI.
Run it on Aurora Linux; it cannot build the Linux
backend on macOS.

Example on an Aurora Linux host:

```sh
sudo install -m755 aurora-windows-vm /usr/local/bin/aurora-windows-vm
sudo install -m755 build-neptune-stack.sh /usr/libexec/aurora-windows-vm/build-neptune-stack.sh
# Run verify-guest-driver.ps1 on Windows, then copy the resulting package.
NPT_D3D12_LIBRARY_PATH=/usr/lib64/libvkd3d-proton-d3d12.so \
  aurora-windows-vm --guest-driver-dir /var/lib/aurora/windows-viogpu3d \
  --disk /var/lib/libvirt/images/windows-arm64.raw
```

When using the pinned stack builder's private prefix, pass
`--host-prefix /path/to/.aurora-neptune/prefix`; the launcher searches its
`lib`/`lib64` directories for DXVK and vkd3d before the system library paths
and prepends those directories to `LD_LIBRARY_PATH` before starting the
private QEMU binary.

The command fails closed if QEMU lacks Neptune or the Vulkan D3D12 backend is
missing. Use `--no-gpu` only for 2D diagnostics.
