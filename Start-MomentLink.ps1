$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Stop-WithError([string]$Message) {
  Write-Host "[FAIL] $Message" -ForegroundColor Red
  exit 1
}

Write-Host "MomentLink startup preflight" -ForegroundColor Cyan
Write-Host "Workspace: $PSScriptRoot"

$envFile = Join-Path $PSScriptRoot ".env"
$envExample = Join-Path $PSScriptRoot ".env.example"
if (!(Test-Path -LiteralPath $envFile)) {
  if (!(Test-Path -LiteralPath $envExample)) { Stop-WithError "Missing .env and .env.example" }
  Copy-Item -LiteralPath $envExample -Destination $envFile
  Write-Host "[WARN] Created .env from .env.example. Cloud/OAuth can be configured later." -ForegroundColor Yellow
} else { Write-Host "[OK] .env found" -ForegroundColor Green }

$port = 8000
$portLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*LOCAL_PORT\s*=' } | Select-Object -First 1
if ($portLine -and $portLine -match '^\s*LOCAL_PORT\s*=\s*(\d+)') { $port = [int]$Matches[1] }
if ($port -lt 1 -or $port -gt 65535) { Stop-WithError "LOCAL_PORT must be between 1 and 65535" }
Write-Host "[OK] Port configured: $port" -ForegroundColor Green

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $python)) {
  $systemPython = Get-Command python -ErrorAction SilentlyContinue
  if (!$systemPython) { Stop-WithError "Python 3.11+ not found. Install Python and retry." }
  & $systemPython.Source -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
  if ($LASTEXITCODE -ne 0) { Stop-WithError "Python 3.11 or newer is required" }
  Write-Host "Creating virtual environment..."
  & $systemPython.Source -m venv (Join-Path $PSScriptRoot ".venv")
  if ($LASTEXITCODE -ne 0) { Stop-WithError "Could not create .venv" }
}
if (!(Test-Path -LiteralPath $python)) { Stop-WithError "Virtual environment Python not found: $python" }
& $python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if ($LASTEXITCODE -ne 0) { Stop-WithError "The .venv Python must be 3.11+. Recreate .venv and retry." }
Write-Host "[OK] Python virtual environment ready" -ForegroundColor Green

$dependencyCheck = "import fastapi, uvicorn, sqlalchemy, watchdog, PIL, cv2, httpx, qrcode, dotenv, multipart"
& $python -c $dependencyCheck 2>$null
if ($LASTEXITCODE -ne 0) {
  $requirements = Join-Path $PSScriptRoot "local\requirements.txt"
  if (!(Test-Path -LiteralPath $requirements)) { Stop-WithError "Missing local\requirements.txt" }
  Write-Host "[WARN] Installing missing Python dependencies..." -ForegroundColor Yellow
  & $python -m pip install -r $requirements
  if ($LASTEXITCODE -ne 0) { Stop-WithError "Dependency installation failed. Check network/proxy and retry." }
}
& $python -c $dependencyCheck 2>$null
if ($LASTEXITCODE -ne 0) { Stop-WithError "Required Python dependencies are still missing. Run setup.bat for details." }
Write-Host "[OK] Required dependencies available" -ForegroundColor Green

& $python -m local.app.setup_local
if ($LASTEXITCODE -ne 0) { Stop-WithError "Local folders or database initialization failed. Check project folder permissions." }
Write-Host "[OK] Local folders and database ready" -ForegroundColor Green

$listeners = @()
try { $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) } catch { }
if ($listeners.Count -gt 0) {
  $pids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
  $existingMomentLink = $false
  try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/healthz" -TimeoutSec 3
    if ($health.ok -eq $true) { $existingMomentLink = $true }
  } catch { }
  if ($existingMomentLink) {
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "  MomentLink is already running" -ForegroundColor Green
    Write-Host "  Opening: http://127.0.0.1:$port/setup" -ForegroundColor Cyan
    Write-Host "  Existing server was left running." -ForegroundColor DarkGray
    Write-Host "==============================================" -ForegroundColor Cyan
    Start-Process "http://127.0.0.1:$port/setup"
    exit 0
  }
  $owners = foreach ($processId in $pids) {
    $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($proc) { "PID $processId ($($proc.ProcessName))" } else { "PID $processId" }
  }
  Stop-WithError "Port $port is occupied by $($owners -join ', '). Stop that app or change LOCAL_PORT in .env. No process was stopped."
}
Write-Host "[OK] Port $port is available" -ForegroundColor Green

$cloudLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*CLOUD_API_URL\s*=' } | Select-Object -First 1
if (!$cloudLine -or $cloudLine -match '^\s*CLOUD_API_URL\s*=\s*$') {
  Write-Host "[WARN] CLOUD_API_URL is empty; local mode works, cloud gallery sync is unavailable." -ForegroundColor Yellow
} else {
  $cloudUrl = ($cloudLine -replace '^\s*CLOUD_API_URL\s*=\s*', '').Trim().Trim('"').Trim("'").TrimEnd('/')
  if ($cloudUrl -notmatch '^https?://') {
    Write-Host "[WARN] CLOUD_API_URL is not a valid HTTP(S) URL; check .env." -ForegroundColor Yellow
  } else {
    try {
      $null = Invoke-WebRequest -Uri "$cloudUrl/healthz" -TimeoutSec 5 -UseBasicParsing
      Write-Host "[OK] Cloud API responded" -ForegroundColor Green
    } catch {
      Write-Host "[WARN] Cloud API is unreachable; local mode can still start and sync can retry later." -ForegroundColor Yellow
    }
  }
}

Write-Host "Starting MomentLink at http://127.0.0.1:$port/setup" -ForegroundColor Cyan
Start-Process "http://127.0.0.1:$port/setup"
& $python -m uvicorn local.app.main:app --host 0.0.0.0 --port $port
if ($LASTEXITCODE -ne 0) { Stop-WithError "Uvicorn exited with code $LASTEXITCODE" }
