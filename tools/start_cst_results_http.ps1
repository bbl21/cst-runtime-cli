param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8124,
    [string]$Path = "/mcp",
    [switch]$ForceRestart
)

$repoRoot = "C:\Users\z1376\Documents\CST_MCP"
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$serverScript = Join-Path $repoRoot "mcp\cst_results_mcp_http.py"
$logDir = Join-Path $repoRoot "tmp"
$stdoutLog = Join-Path $logDir "cst_results_http_stdout.log"
$stderrLog = Join-Path $logDir "cst_results_http_stderr.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$running = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "python" -and $_.CommandLine -match "cst_results_mcp_http.py"
    }

if ($running -and -not $ForceRestart) {
    Write-Output "cst-results-http 已在运行"
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
