# Dot-source from any directory: . ./scripts/dev-tools.ps1
# Session-only PATH and project-local caches; no machine settings are changed.
$cascadeRoot = Split-Path -Parent $PSScriptRoot
$cascadeUvBin = Join-Path $env:USERPROFILE '.local/bin'
$cascadeFoundry = Join-Path $cascadeRoot '.tools/foundry/node_modules/@foundry-rs'
$cascadeToolPaths = @($cascadeUvBin)
foreach ($cascadeTool in @('forge', 'anvil', 'cast')) {
    $cascadeToolPaths += Join-Path $cascadeFoundry "$cascadeTool-win32-amd64/bin"
}
$env:PATH = ($cascadeToolPaths -join ';') + ';' + $env:PATH
$env:UV_CACHE_DIR = Join-Path $cascadeRoot '.cache/uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $cascadeRoot '.tools/python'
$env:SVM_HOME = Join-Path $cascadeRoot '.tools/solc'
