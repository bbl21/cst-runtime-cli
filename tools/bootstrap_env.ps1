<#
Bootstrap script: installs Python 3.13 (64-bit) and sets up a venv with uv for this repo.
Note: This script assumes internet access and admin rights for a system-wide Python install.
#>
$projectRoot = (Get-Location).Path
$venvPath = Join-Path $projectRoot ".venv"

function Get-PythonExe {
  # Try common install locations first
  $candidates = @(
    "$Env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "C:\Python313\python.exe",
    "C:\Program Files\Python313\python.exe",
    "C:\Program Files (x86)\Python313\python.exe"
  )
  foreach ($p in $candidates) {
    # Skip Windows Store shim paths to avoid non-fully-featured interpreters
    if ($p -like '*WindowsApps*') { continue }
    if (Test-Path $p) { return $p }
  }
  # Fall back to system python if already on PATH
  $py = Get-Command python -ErrorAction SilentlyContinue
  if ($py) {
    if ($py.Source -like '*WindowsApps*') { return $null }
    return $py.Source
  }
  return $null
}

$pythonExe = Get-PythonExe
if (-not $pythonExe) {
  Write-Host "Python 3.13 not found. Installing Python 3.13 (64-bit) for all users..."
  $installerUrl = "https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe"
  $tempInstaller = Join-Path $Env:TEMP "python-3.13.0-amd64.exe"
  try {
    Write-Host "Downloading Python 3.13..."
    Invoke-WebRequest -Uri $installerUrl -OutFile $tempInstaller -UseBasicParsing
    Write-Host "Installing Python 3.13..."
    $args = "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0 TargetDir=`"C:\\Python313`""
    Start-Process -FilePath $tempInstaller -ArgumentList $args -Wait -NoNewWindow
    Remove-Item $tempInstaller -Force
    if (Test-Path "C:\Python313\python.exe") {
      $pythonExe = "C:\Python313\python.exe"
    } else {
      Write-Error "Python installation did not place python.exe where expected."
      exit 1
    }
  } catch {
    Write-Error "Failed to install Python: $_"
    exit 1
  }
}
Write-Host "Using Python at: $pythonExe"

if (-not (Test-Path $venvPath)) {
  & $pythonExe -m venv ".venv"
  Write-Host "Created virtual environment at .venv"
} else {
  Write-Host "Virtual environment already exists at .venv"
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  Write-Error "Expected venv Python at $venvPython not found."
  exit 1
}
# Ensure pip exists in the virtual environment, fall back to ensurepip if needed
try {
  & $venvPython -m pip --version | Out-Null
} catch {
  Write-Host "Pip not found in venv, attempting to bootstrap via ensurepip..."
  & $venvPython -m ensurepip --upgrade
}
# Upgrade pip to latest and install uv
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install uv
Write-Host "uv installed in virtual environment."

Write-Host "Bootstrap complete. Activate with: .\.venv\Scripts\Activate.ps1"
