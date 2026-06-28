param(
    [string]$COM_PORT = "COM5"
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Building Phantom Scan ESP32 CSI Node    " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Ensure we are in the correct directory
$CsiNodeDir = Join-Path $PSScriptRoot "firmware\esp32-csi-node"
if (-Not (Test-Path $CsiNodeDir)) {
    Write-Error "Could not find firmware directory at $CsiNodeDir"
    exit 1
}

Set-Location $CsiNodeDir

Write-Host "Running idf.py build..." -ForegroundColor Yellow
idf.py build

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed!"
    exit $LASTEXITCODE
}

Write-Host "`nBuild successful! Flashing to $COM_PORT..." -ForegroundColor Green
idf.py -p $COM_PORT flash monitor

if ($LASTEXITCODE -ne 0) {
    Write-Error "Flashing failed!"
    exit $LASTEXITCODE
}
