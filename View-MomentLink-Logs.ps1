$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$logFile = Join-Path $projectRoot "local\logs\photoflow.log"
if (!(Test-Path -LiteralPath $logFile)) {
  Write-Host "Backend log has not been created yet:" -ForegroundColor Yellow
  Write-Host $logFile
  Write-Host "Start MomentLink first, then run this viewer again."
  exit 1
}
Write-Host "Following backend log (Ctrl+C to stop): $logFile" -ForegroundColor Cyan
Get-Content -LiteralPath $logFile -Tail 100 -Wait
