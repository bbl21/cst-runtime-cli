param(
    [string]$ProjectRoot = "",
    [string]$CstLibraryPath = "C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries",
    [string]$BindHost = "127.0.0.1",
    [int]$ModelerPort = 8123,
    [int]$ResultsPort = 8124,
    [string]$Path = "/mcp",
    [switch]$SkipDependencyInstall,
    [switch]$SkipStart,
    [switch]$SkipVerify,
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = Split-Path -Parent $scriptDir
}
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path

$tmpDir = Join-Path $ProjectRoot "tmp"
$codexDir = Join-Path $ProjectRoot ".codex"
$configPath = Join-Path $codexDir "config.toml"
$modelerUrl = "http://$BindHost`:$ModelerPort$Path"
$resultsUrl = "http://$BindHost`:$ResultsPort$Path"

New-Item -ItemType Directory -Force -Path $tmpDir, $codexDir | Out-Null

Write-Output "== CST_MCP MCP one-click install =="
Write-Output "project: $ProjectRoot"
Write-Output "modeler: $modelerUrl"
Write-Output "results: $resultsUrl"

$setupArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $ProjectRoot "tools\setup_portable_workspace.ps1"),
    "-ProjectRoot", $ProjectRoot,
    "-CstLibraryPath", $CstLibraryPath
)
if ($SkipDependencyInstall) {
    $setupArgs += "-SkipDependencyInstall"
}

Write-Output "== setup workspace =="
& powershell @setupArgs
if ($LASTEXITCODE -ne 0) {
    throw "setup_portable_workspace.ps1 failed with exit code $LASTEXITCODE"
}

if (Test-Path -LiteralPath $configPath -PathType Leaf) {
    $backupPath = Join-Path $codexDir ("config.toml.{0}.bak" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
    Copy-Item -LiteralPath $configPath -Destination $backupPath -Force
    Write-Output "backup config: $backupPath"
}

$configText = @"
[mcp_servers.cst-modeler-http]
url = "$modelerUrl"

[mcp_servers.cst-results-http]
url = "$resultsUrl"

[mcp_servers.cst-results-http.tools.list_result_items]
approval_mode = "approve"
"@
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($configPath, $configText, $utf8NoBom)
Write-Output "wrote MCP config: $configPath"

if (-not $SkipStart) {
    Write-Output "== start MCP services =="
    $modelerStartArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $ProjectRoot "tools\start_advanced_mcp_http.ps1"),
        "-ProjectRoot", $ProjectRoot,
        "-BindHost", $BindHost,
        "-Port", "$ModelerPort",
        "-Path", $Path
    )
    if ($ForceRestart) {
        $modelerStartArgs += "-ForceRestart"
    }
    & powershell @modelerStartArgs
    if ($LASTEXITCODE -ne 0) {
        throw "start_advanced_mcp_http.ps1 failed with exit code $LASTEXITCODE"
    }

    $resultsStartArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $ProjectRoot "tools\start_cst_results_http.ps1"),
        "-ProjectRoot", $ProjectRoot,
        "-BindHost", $BindHost,
        "-Port", "$ResultsPort",
        "-Path", $Path
    )
    if ($ForceRestart) {
        $resultsStartArgs += "-ForceRestart"
    }
    & powershell @resultsStartArgs
    if ($LASTEXITCODE -ne 0) {
        throw "start_cst_results_http.ps1 failed with exit code $LASTEXITCODE"
    }
}

if (-not $SkipVerify) {
    Write-Output "== verify MCP tools/list =="
    $pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        throw "Python executable not found after setup: $pythonExe"
    }

    $modelerList = Join-Path $tmpDir "mcp_one_click_modeler_tools.json"
    $resultsList = Join-Path $tmpDir "mcp_one_click_results_tools.json"

    & $pythonExe (Join-Path $ProjectRoot "tools\call_mcp_tool.py") `
        --url $modelerUrl --list-only --include-tool-names --timeout-seconds 15 --output-file $modelerList
    if ($LASTEXITCODE -ne 0) {
        throw "modeler MCP tools/list failed"
    }

    & $pythonExe (Join-Path $ProjectRoot "tools\call_mcp_tool.py") `
        --url $resultsUrl --list-only --include-tool-names --timeout-seconds 15 --output-file $resultsList
    if ($LASTEXITCODE -ne 0) {
        throw "results MCP tools/list failed"
    }

    Write-Output "modeler tools/list: $modelerList"
    Write-Output "results tools/list: $resultsList"
}

$result = [ordered]@{
    status = "success"
    project_root = $ProjectRoot
    config_path = $configPath
    modeler_url = $modelerUrl
    results_url = $resultsUrl
    started = -not [bool]$SkipStart
    verified = -not [bool]$SkipVerify
}

$result | ConvertTo-Json -Depth 4
