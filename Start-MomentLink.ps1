$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Write-Check([string]$Message) { Write-Host "[OK]   $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Stop-WithError([string]$Message) {
  Write-Host "[FAIL] $Message" -ForegroundColor Red
  Write-Host "แก้ไขตามข้อความด้านบนแล้วเปิด Start-MomentLink.ps1 ใหม่อีกครั้ง"
  exit 1
}

Write-Host "MomentLink startup check" -ForegroundColor Cyan
Write-Host "Workspace: $PSScriptRoot"

# Load defaults on first run; local mode remains usable without cloud settings.
$envFile = Join-Path $PSScriptRoot ".env"
$envExample = Join-Path $PSScriptRoot ".env.example"
if (!(Test-Path -LiteralPath $envFile)) {
  if (!(Test-Path -LiteralPath $envExample)) { Stop-WithError "ไม่พบทั้ง .env และ .env.example" }
  Copy-Item -LiteralPath $envExample -Destination $envFile
  Write-Warn "สร้าง .env จาก .env.example แล้ว (ตั้งค่า Cloud/OAuth ภายหลังได้)"
} else { Write-Check ".env พร้อมใช้งาน" }

$port = 8000
$portLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*LOCAL_PORT\s*=' } | Select-Object -First 1
if ($portLine -and $portLine -match '^\s*LOCAL_PORT\s*=\s*(\d+)') { $port = [int]$Matches[1] }
if ($port -lt 1 -or $port -gt 65535) { Stop-WithError "LOCAL_PORT ใน .env ต้องอยู่ระหว่าง 1 ถึง 65535" }
Write-Check "พอร์ตที่ตั้งไว้: $port"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $python)) {
  $systemPython = Get-Command python -ErrorAction SilentlyContinue
  if (!$systemPython) { Stop-WithError "ไม่พบ Python 3.11 ขึ้นไป ติดตั้ง Python แล้วเปิดสคริปต์ใหม่" }
  & $systemPython.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
  if ($LASTEXITCODE -ne 0) { Stop-WithError "ต้องใช้ Python 3.11 ขึ้นไป" }
  Write-Host "กำลังสร้าง virtual environment..."
  & $systemPython.Source -m venv (Join-Path $PSScriptRoot ".venv")
  if ($LASTEXITCODE -ne 0) { Stop-WithError "สร้าง .venv ไม่สำเร็จ" }
}
if (!(Test-Path -LiteralPath $python)) { Stop-WithError "ไม่พบ Python ใน .venv: $python" }
& $python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if ($LASTEXITCODE -ne 0) { Stop-WithError "Python ใน .venv เก่ากว่า 3.11 ให้ลบ .venv แล้วรัน setup.bat ใหม่" }
Write-Check "Python virtual environment พร้อมใช้งาน"

# Install dependencies only when the app's required import set is incomplete.
$dependencyCheck = "import fastapi, uvicorn, sqlalchemy, watchdog, PIL, cv2, httpx, qrcode, dotenv, multipart"
& $python -c $dependencyCheck 2>$null
if ($LASTEXITCODE -ne 0) {
  $requirements = Join-Path $PSScriptRoot "local\requirements.txt"
  if (!(Test-Path -LiteralPath $requirements)) { Stop-WithError "ไม่พบ local\requirements.txt" }
  Write-Warn "dependencies ยังไม่ครบ กำลังติดตั้งจาก local\requirements.txt"
  & $python -m pip install -r $requirements
  if ($LASTEXITCODE -ne 0) { Stop-WithError "ติดตั้ง dependencies ไม่สำเร็จ ตรวจอินเทอร์เน็ตหรือ proxy แล้วลองใหม่" }
}
& $python -c $dependencyCheck 2>$null
if ($LASTEXITCODE -ne 0) { Stop-WithError "ตรวจ dependencies ไม่ผ่าน แม้ติดตั้งแล้ว กรุณารัน setup.bat เพื่อตรวจรายละเอียด" }
Write-Check "dependencies หลักครบ"

# Initialize directories and database before opening the browser/server.
& $python -m local.app.setup_local
if ($LASTEXITCODE -ne 0) { Stop-WithError "เตรียมโฟลเดอร์หรือฐานข้อมูลไม่สำเร็จ ตรวจสิทธิ์เขียนในโฟลเดอร์โปรเจกต์" }
Write-Check "โฟลเดอร์และฐานข้อมูลพร้อมใช้งาน"

# Never kill an unrelated process automatically. Detect an existing app or report its owner.
$listeners = @()
try { $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) } catch { }
if ($listeners.Count -gt 0) {
  $pids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
  $existingMomentLink = $false
  try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -TimeoutSec 3 -UseBasicParsing
    if ($response.StatusCode -eq 200) { $existingMomentLink = $true }
  } catch { }
  if ($existingMomentLink) {
    Write-Warn "มีเว็บตอบสนองอยู่แล้วที่ http://127.0.0.1:$port — เปิดหน้าระบบเดิมให้"
    Start-Process "http://127.0.0.1:$port/setup"
    exit 0
  }
  $owners = foreach ($processId in $pids) {
    $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($proc) { "PID $processId ($($proc.ProcessName))" } else { "PID $processId" }
  }
  Stop-WithError "พอร์ต $port ถูกใช้งานแล้ว: $($owners -join ', '). ปิดโปรแกรมนั้นหรือเปลี่ยน LOCAL_PORT ใน .env; สคริปต์จะไม่หยุดโปรเซสอื่นให้อัตโนมัติ"
}
Write-Check "พอร์ต $port ว่าง"

# Cloud is optional for local capture. Warn rather than blocking offline/local workflows.
$cloudLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*CLOUD_API_URL\s*=' } | Select-Object -First 1
if (!$cloudLine -or $cloudLine -match '^\s*CLOUD_API_URL\s*=\s*$') {
  Write-Warn "ยังไม่ได้ตั้ง CLOUD_API_URL — ระบบ local ใช้ได้ แต่การ sync ขึ้น Gallery จะยังไม่ทำงาน"
} else {
  $cloudUrl = ($cloudLine -replace '^\s*CLOUD_API_URL\s*=\s*', '').Trim().Trim('"').Trim("'").TrimEnd('/')
  if ($cloudUrl -notmatch '^https?://') { Write-Warn "CLOUD_API_URL รูปแบบไม่ถูกต้อง; ตรวจค่าใน .env ก่อนใช้งาน sync" }
  else {
    try {
      $null = Invoke-WebRequest -Uri "$cloudUrl/healthz" -TimeoutSec 5 -UseBasicParsing
      Write-Check "Cloud API ตอบสนอง"
    } catch { Write-Warn "ติดต่อ Cloud API ไม่สำเร็จตอน preflight; local ยังเริ่มได้ และระบบจะลอง sync ใหม่ภายหลัง" }
  }
}

Write-Host ""
Write-Host "เริ่ม MomentLink ที่ http://127.0.0.1:$port/setup" -ForegroundColor Cyan
Start-Process "http://127.0.0.1:$port/setup"
& $python -m uvicorn local.app.main:app --host 0.0.0.0 --port $port
if ($LASTEXITCODE -ne 0) { Stop-WithError "Uvicorn หยุดทำงานด้วย exit code $LASTEXITCODE" }
