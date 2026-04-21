param(
    [string]$ProjectRoot = ""
)

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot = Split-Path -Parent $scriptDir
} else {
    $repoRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$serverScript = Join-Path $repoRoot "mcp\cst_results_mcp_http.py"
$escapedServerScript = [regex]::Escape($serverScript)

$running = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "python" -and $_.CommandLine -match $escapedServerScript
    }

if (-not $running) {
    Write-Output "cst-results-http not running"
    exit 0
}

$running | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Output ("stopped pid={0}" -f $_.ProcessId)
}
