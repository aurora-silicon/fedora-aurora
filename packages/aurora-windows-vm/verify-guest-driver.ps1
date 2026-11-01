param(
  [Parameter(Mandatory=$true)][string]$Package,
  [string]$Output = "driver-signature.txt"
)
$ErrorActionPreference = "Stop"
$cat = Join-Path $Package "viogpu3d.cat"
$sys = Join-Path $Package "viogpu3d.sys"
$inf = Join-Path $Package "viogpu3d.inf"
$required = @($cat, $sys, $inf,
  (Join-Path $Package "neptune_umd.dll"),
  (Join-Path $Package "vulkan_virtio.dll"),
  (Join-Path $Package "virtio_icd.json"))
foreach ($path in $required) {
  if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing $path" }
}
$sig = Get-AuthenticodeSignature -LiteralPath $cat
if ($sig.Status -ne "Valid") { throw "Invalid catalog signature: $($sig.Status)" }
$machine = (Get-Command signtool.exe -ErrorAction Stop | Select-Object -First 1).Source
& $machine verify /pa /all $cat | Out-Null
if ($LASTEXITCODE -ne 0) { throw "signtool rejected the catalog" }
$arch = (dumpbin /headers $sys 2>$null | Select-String -Pattern "AA64 machine" -Quiet)
if (!$arch) { throw "viogpu3d.sys is not an ARM64 (AA64) driver" }
@(
  "Authenticode=valid"
  "Architecture=ARM64"
  "Catalog=$((Get-FileHash $cat -Algorithm SHA256).Hash.ToLowerInvariant())"
  "Driver=$((Get-FileHash $sys -Algorithm SHA256).Hash.ToLowerInvariant())"
  "VerifiedBy=Get-AuthenticodeSignature+signtool"
) | Set-Content -LiteralPath (Join-Path $Package $Output) -Encoding ascii
Write-Host "Wrote $(Join-Path $Package $Output)"
