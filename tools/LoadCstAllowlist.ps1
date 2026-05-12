function Get-CstForceKillAllowlist {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot = Split-Path -Parent $scriptDir
    $configPath = Join-Path $repoRoot "cst_process_allowlist.json"
    
    $defaultAllowlist = @(
        'cstd',
        'CST DESIGN ENVIRONMENT_AMD64',
        'CSTDCMainController_AMD64',
        'CSTDCSolverServer_AMD64'
    )
    
    if (-not (Test-Path $configPath)) {
        Write-Warning "CST process allowlist config not found at $configPath, using default"
        return $defaultAllowlist
    }
    
    try {
        $config = Get-Content $configPath -Raw | ConvertFrom-Json
        $allowlist = $config.cst_force_kill_process_allowlist
        
        if (-not $allowlist -or $allowlist.Count -eq 0) {
            Write-Warning "Empty allowlist in $configPath, using default"
            return $defaultAllowlist
        }
        
        return $allowlist
    } catch {
        Write-Warning "Failed to load allowlist from $configPath : $($_.Exception.Message), using default"
        return $defaultAllowlist
    }
}
