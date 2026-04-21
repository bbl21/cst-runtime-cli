param(
    [string]$ProjectRoot = "",
    [string]$CstLibraryPath = "C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = Split-Path -Parent $scriptDir
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$pyproject = Join-Path $ProjectRoot "pyproject.toml"
if (-not (Test-Path -LiteralPath $pyproject -PathType Leaf)) {
    throw "pyproject.toml not found: $pyproject"
}

if (-not (Test-Path -LiteralPath $CstLibraryPath -PathType Container)) {
    throw "CST Python library path not found: $CstLibraryPath"
}

$escapedCstPath = $CstLibraryPath.Replace("\", "\\")
$pyprojectText = Get-Content -LiteralPath $pyproject -Raw -Encoding UTF8
$updatedText = [regex]::Replace(
    $pyprojectText,
    'cst-studio-suite-link\s*=\s*\{\s*path\s*=\s*"[^"]+"\s*,\s*editable\s*=\s*true\s*\}',
    "cst-studio-suite-link = { path = `"$escapedCstPath`", editable = true }"
)
if ($updatedText -ne $pyprojectText) {
    Set-Content -LiteralPath $pyproject -Encoding UTF8 -Value $updatedText
    Write-Output "updated CST library path in pyproject.toml"
}

if (-not $SkipDependencyInstall) {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    $venvUv = Join-Path $ProjectRoot ".venv\Scripts\uv.exe"
    if ($uv) {
        Push-Location $ProjectRoot
        try {
            & $uv.Source sync
            if ($LASTEXITCODE -ne 0) {
                throw "uv sync failed with exit code $LASTEXITCODE"
            }
        } finally {
            Pop-Location
        }
    } elseif (Test-Path -LiteralPath $venvUv -PathType Leaf) {
        Push-Location $ProjectRoot
        try {
            & $venvUv sync
            if ($LASTEXITCODE -ne 0) {
                throw "uv sync failed with exit code $LASTEXITCODE"
            }
        } finally {
            Pop-Location
        }
    } else {
        throw "uv not found. Install uv first, or run tools/bootstrap_env.ps1 if this machine can install Python and uv."
    }
}

if ($SkipDependencyInstall) {
    & (Join-Path $ProjectRoot "tools\verify_portable_install.ps1") -ProjectRoot $ProjectRoot -CstLibraryPath $CstLibraryPath -SkipPythonCompile
} else {
    & (Join-Path $ProjectRoot "tools\verify_portable_install.ps1") -ProjectRoot $ProjectRoot -CstLibraryPath $CstLibraryPath
}
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Output "Portable workspace is ready."
Write-Output "Start modeler MCP: powershell -ExecutionPolicy Bypass -File tools/start_advanced_mcp_http.ps1"
Write-Output "Start results MCP: powershell -ExecutionPolicy Bypass -File tools/start_cst_results_http.ps1"
