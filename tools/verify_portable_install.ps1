param(
    [string]$ProjectRoot = "",
    [string]$CstLibraryPath = "C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries",
    [switch]$SkipPythonCompile,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = Split-Path -Parent $scriptDir
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$checks = New-Object System.Collections.Generic.List[object]

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Message
    )
    $checks.Add([ordered]@{
        name = $Name
        ok = $Ok
        message = $Message
    }) | Out-Null
}

function Test-RequiredPath {
    param(
        [string]$Name,
        [string]$RelativePath,
        [string]$Type
    )
    $path = Join-Path $ProjectRoot $RelativePath
    if ($Type -eq "Directory") {
        Add-Check -Name $Name -Ok (Test-Path -LiteralPath $path -PathType Container) -Message $RelativePath
    } else {
        Add-Check -Name $Name -Ok (Test-Path -LiteralPath $path -PathType Leaf) -Message $RelativePath
    }
}

Test-RequiredPath -Name "AGENTS rules" -RelativePath "AGENTS.md" -Type "File"
Test-RequiredPath -Name "project plan" -RelativePath "docs\project-goals-and-plan.md" -Type "File"
Test-RequiredPath -Name "priority checklist" -RelativePath "docs\current-priority-checklist.md" -Type "File"
Test-RequiredPath -Name "phase B handoff" -RelativePath "docs\phase-b-main-chain-consolidation.md" -Type "File"
Test-RequiredPath -Name "phase C portable mode" -RelativePath "docs\phase-c-system-integration-and-portable-mode.md" -Type "File"
Test-RequiredPath -Name "formal skill" -RelativePath "skills\cst-simulation-optimization\SKILL.md" -Type "File"
Test-RequiredPath -Name "active codex skill copy" -RelativePath ".codex\cst-simulation-optimization\SKILL.md" -Type "File"
Test-RequiredPath -Name "modeler mcp" -RelativePath "mcp\advanced_mcp.py" -Type "File"
Test-RequiredPath -Name "results mcp" -RelativePath "mcp\cst_results_mcp.py" -Type "File"
Test-RequiredPath -Name "modeler http launcher" -RelativePath "tools\start_advanced_mcp_http.ps1" -Type "File"
Test-RequiredPath -Name "results http launcher" -RelativePath "tools\start_cst_results_http.ps1" -Type "File"
Test-RequiredPath -Name "one-click MCP installer" -RelativePath "tools\install_mcp_one_click.ps1" -Type "File"
Test-RequiredPath -Name "MCP client helper" -RelativePath "tools\call_mcp_tool.py" -Type "File"

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
$venvUv = Join-Path $ProjectRoot ".venv\Scripts\uv.exe"
Add-Check -Name "uv available" -Ok (($null -ne $uvCommand) -or (Test-Path -LiteralPath $venvUv -PathType Leaf)) -Message "uv on PATH or .venv\Scripts\uv.exe"

$pythonVersionFile = Join-Path $ProjectRoot ".python-version"
if (Test-Path -LiteralPath $pythonVersionFile -PathType Leaf) {
    $pyVersion = (Get-Content -LiteralPath $pythonVersionFile -Encoding UTF8 | Select-Object -First 1).Trim()
    Add-Check -Name "python version file" -Ok ($pyVersion -eq "3.13") -Message ".python-version=$pyVersion"
} else {
    Add-Check -Name "python version file" -Ok $false -Message ".python-version missing"
}

Add-Check -Name "CST python libraries" -Ok (Test-Path -LiteralPath $CstLibraryPath -PathType Container) -Message $CstLibraryPath

if (-not $SkipPythonCompile) {
    $pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $pythonExe -PathType Leaf) {
        $compile = & $pythonExe -m py_compile `
            (Join-Path $ProjectRoot "mcp\advanced_mcp.py") `
            (Join-Path $ProjectRoot "mcp\cst_results_mcp.py") `
            (Join-Path $ProjectRoot "tools\call_mcp_tool.py") 2>&1
        Add-Check -Name "python compile" -Ok ($LASTEXITCODE -eq 0) -Message (($compile | Out-String).Trim())
    } else {
        Add-Check -Name "python compile" -Ok $false -Message ".venv\Scripts\python.exe missing; run setup_portable_workspace.ps1 first"
    }
}

$failed = @($checks | Where-Object { -not $_.ok })
$result = [ordered]@{
    status = $(if ($failed.Count -eq 0) { "success" } else { "error" })
    project_root = $ProjectRoot
    checked_at = (Get-Date).ToString("o")
    checks = $checks
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8
} else {
    foreach ($check in $checks) {
        $mark = if ($check.ok) { "[OK]" } else { "[FAIL]" }
        Write-Output "$mark $($check.name): $($check.message)"
    }
    if ($failed.Count -gt 0) {
        Write-Error "Portable install verification failed: $($failed.Count) check(s) failed."
        exit 1
    }
    Write-Output "Portable install verification passed."
}
