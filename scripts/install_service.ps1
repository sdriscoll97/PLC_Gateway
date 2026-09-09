param([string]$Python="py",[string]$ServiceName="PLCGateway",[string]$BindHost="127.0.0.1",[int]$Port=8443)
$ErrorActionPreference="Stop"
$root=Split-Path -Parent $PSScriptRoot
Set-Location $root
if (!(Test-Path .venv)) { & $Python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
$python=(Resolve-Path .\.venv\Scripts\python.exe).Path
$app=(Resolve-Path .\PLCGateway\app.py).Path
Write-Host "Dependencies installed."
Write-Host "For a Windows Service, install an approved service wrapper (NSSM or WinSW), then configure:"
Write-Host "  executable: $python"
Write-Host "  arguments: -m uvicorn PLCGateway.app:app --host $BindHost --port $Port"
Write-Host "  working directory: $root"
Write-Host "Configure automatic startup and recovery per your server standard. Keep bind host loopback until IIS/HTTPS review is complete."
