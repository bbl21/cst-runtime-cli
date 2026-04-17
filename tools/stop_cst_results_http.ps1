$running = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "python" -and $_.CommandLine -match "cst_results_mcp_http.py"
    }

if (-not $running) {
    Write-Output "cst-results-http not running"
    exit 0
}

$running | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Output "stopped pid=$($_.ProcessId)"
}
