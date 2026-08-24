$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$port = 8000
$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listeners) {
  Write-Host "Port $port is already in use:"
  $listeners | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table
  $answer = Read-Host "Stop existing MomentLink/Python process on port $port? (y/N)"
  if ($answer -match "^[Yy]") {
    foreach ($listener in $listeners) {
      Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
  } else {
    Write-Host "Canceled. Open http://127.0.0.1:8000 if the existing server is MomentLink."
    exit 0
  }
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $python)) {
  Write-Host "Python venv not found: $python"
  Write-Host "Create/install dependencies before starting MomentLink."
  pause
  exit 1
}

Start-Process "http://127.0.0.1:$port/setup"
& $python -m uvicorn local.app.main:app --host 0.0.0.0 --port $port
