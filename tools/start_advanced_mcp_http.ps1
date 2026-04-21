param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8123,
    [string]$Path = "/mcp",
    [string]$ProjectRoot = "",
    [switch]$ForceRestart
)

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot = Split-Path -Parent $scriptDir
} else {
    $repoRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$serverScript = Join-Path $repoRoot "mcp\advanced_mcp_http.py"
$logDir = Join-Path $repoRoot "tmp"
$stdoutLog = Join-Path $logDir "advanced_mcp_http_stdout.log"
$stderrLog = Join-Path $logDir "advanced_mcp_http_stderr.log"

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "Python executable not found: $pythonExe. Run tools/setup_portable_workspace.ps1 first."
}
if (-not (Test-Path -LiteralPath $serverScript -PathType Leaf)) {
    throw "MCP server script not found: $serverScript"
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$escapedServerScript = [regex]::Escape($serverScript)
$running = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "python" -and $_.CommandLine -match $escapedServerScript
    }

if ($running -and -not $ForceRestart) {
    Write-Output "cst-modeler-http already running"
    $running | Select-Object ProcessId, CommandLine
    exit 0
}

if ($running) {
    $running | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

Remove-Item $stdoutLog, $stderrLog -Force -ErrorAction SilentlyContinue

$process = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList @($serverScript, "--host", $BindHost, "--port", "$Port", "--path", $Path) `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 2

Write-Output "started pid=$($process.Id) url=http://$BindHost`:$Port$Path"
