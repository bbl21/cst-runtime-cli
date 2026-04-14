Stop-Process -Name "cstd" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "CST DESIGN ENVIRONMENT_AMD64" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "CSTDCMainController_AMD64" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "CSTDCSolverServer_AMD64" -Force -ErrorAction SilentlyContinue
Write-Output "CST processes killed"
