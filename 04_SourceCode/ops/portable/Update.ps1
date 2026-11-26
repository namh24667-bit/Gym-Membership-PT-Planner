param([string]$Package, [switch]$Rollback, [string]$OfflineWheels, [string]$InstalledRoot, [string]$SHA256)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$target = if ($InstalledRoot) { (Resolve-Path -LiteralPath $InstalledRoot).Path } else { $root }
$python = Join-Path $target '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Can cai dat truoc.' }
$tool = Join-Path $PSScriptRoot 'release.py'
if ($Rollback) {
    & $python -X utf8 -I -B $tool rollback --target $target
} else {
    if (-not $Package) { $Package = (Read-Host 'Duong dan ZIP ban moi').Trim('"') }
    $invokeArgs = @($tool, 'update', $Package, '--target', $target)
    if ($SHA256) { $invokeArgs += @('--sha256', $SHA256) }
    if ($OfflineWheels) { $invokeArgs += @('--offline-wheels', $OfflineWheels) }
    & $python -X utf8 -I -B @invokeArgs
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'Chay Mo-IronPulse.cmd de xac minh dang nhap va khoi dong ban vua cap nhat.'
