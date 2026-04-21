param(
    [string]$OutputDir = "dist",
    [string]$BundleName = "",
    [switch]$IncludeRef,
    [switch]$IncludeTasks,
    [switch]$IncludePrototypeData
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

if ([string]::IsNullOrWhiteSpace($BundleName)) {
    $BundleName = "cst_mcp_portable_$timestamp"
}

$outputPath = Join-Path $repoRoot $OutputDir
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$stagingRoot = Join-Path $env:TEMP "$BundleName"
if (Test-Path $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null

$requiredFiles = @(
    ".python-version",
    "AGENTS.md",
    "MEMORY.md",
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
    "startup_prototype_optimizer.ps1"
)

$requiredDirs = @(
    "mcp",
    "skills",
    ".codex",
    "docs",
    "tools",
    "prototype_optimizer"
)

if ($IncludeRef) {
    $requiredDirs += "ref"
}

if ($IncludeTasks) {
    $requiredDirs += "tasks"
}

function Copy-RepoItem {
    param(
        [string]$RelativePath
    )
    $source = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path $source)) {
        return
    }
    $target = Join-Path $stagingRoot $RelativePath
    $targetParent = Split-Path -Parent $target
    if (-not [string]::IsNullOrWhiteSpace($targetParent)) {
        New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
}

foreach ($file in $requiredFiles) {
    Copy-RepoItem -RelativePath $file
}

foreach ($dir in $requiredDirs) {
    Copy-RepoItem -RelativePath $dir
}

$cleanupPatterns = @(
    ".git",
    ".venv",
    ".ruff_cache",
    ".trae",
    ".workbuddy",
    "__pycache__",
    "tmp",
    "dist",
    "backup",
    "plot_previews"
)

foreach ($pattern in $cleanupPatterns) {
    Get-ChildItem -LiteralPath $stagingRoot -Force -Recurse -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq $pattern } |
        Sort-Object FullName -Descending |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
}

if (-not $IncludePrototypeData) {
    $prototypeData = Join-Path $stagingRoot "prototype_optimizer\data"
    if (Test-Path $prototypeData) {
        Remove-Item -LiteralPath $prototypeData -Recurse -Force
    }
}

Get-ChildItem -LiteralPath $stagingRoot -Force -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Extension -in @(".lok", ".tmp", ".pyc", ".pyo") -or
        $_.Name -like "*.log" -or
        $_.Name -like "*.bak"
    } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }

$manifest = [ordered]@{
    bundle_name = $BundleName
    generated_at = (Get-Date).ToString("o")
    source_repo = $repoRoot
    portable_mode = "system_base"
    include_ref = [bool]$IncludeRef
    include_tasks = [bool]$IncludeTasks
    include_prototype_data = [bool]$IncludePrototypeData
    formal_entry = "tasks/task_xxx_slug -> cst-modeler.prepare_new_run(task_path=...)"
    required_runtime = @{
        python = ">=3.13"
        cst = "CST Studio Suite 2026"
        uv = "required"
        mcp = ">=1.25.0"
    }
    setup = @(
        "powershell -ExecutionPolicy Bypass -File tools/install_mcp_one_click.ps1",
        "powershell -ExecutionPolicy Bypass -File tools/setup_portable_workspace.ps1",
        "powershell -ExecutionPolicy Bypass -File tools/verify_portable_install.ps1"
    )
    mcp_services = @{
        modeler = "tools/start_advanced_mcp_http.ps1"
        results = "tools/start_cst_results_http.ps1"
    }
}

$manifestPath = Join-Path $stagingRoot "PORTABLE_MANIFEST.json"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$readmePath = Join-Path $stagingRoot "PORTABLE_README.md"
@"
# CST_MCP Portable Bundle

## First Run

Run from this extracted directory:

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_mcp_one_click.ps1
```

This initializes dependencies, writes `.codex/config.toml`, starts both HTTP MCP services, and verifies `tools/list`.

## Formal Entry

Use `tasks/task_xxx_slug/` as task context, then start with:

```text
cst-modeler.prepare_new_run(task_path="tasks/task_xxx_slug")
```

The production chain is documented in `docs/phase-b-main-chain-consolidation.md` and `docs/phase-c-system-integration-and-portable-mode.md`.
"@ | Set-Content -LiteralPath $readmePath -Encoding UTF8

$zipPath = Join-Path $outputPath "$BundleName.zip"
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $zipPath -Force

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath
$result = [ordered]@{
    status = "success"
    bundle = $zipPath
    sha256 = $hash.Hash
    staging_root = $stagingRoot
    include_ref = [bool]$IncludeRef
    include_tasks = [bool]$IncludeTasks
    include_prototype_data = [bool]$IncludePrototypeData
}

$result | ConvertTo-Json -Depth 4
