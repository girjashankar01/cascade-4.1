# Official prebuilt Windows x64 binaries; no global install or shell postinstall.
$cascadeRoot = Split-Path -Parent $PSScriptRoot
if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'This helper requires Windows x64. Use the official Foundry installer on other platforms.'
}
npm install --prefix (Join-Path $cascadeRoot '.tools/foundry') --save-exact --ignore-scripts --no-audit --no-fund '@foundry-rs/forge-win32-amd64@1.7.1' '@foundry-rs/anvil-win32-amd64@1.7.1' '@foundry-rs/cast-win32-amd64@1.7.1'
if ($LASTEXITCODE -ne 0) { throw 'Foundry installation failed.' }
Write-Output 'Foundry installed. Load session tools with: . ./scripts/dev-tools.ps1'
