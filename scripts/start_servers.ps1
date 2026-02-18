$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (!(Test-Path "runtime_logs")) {
  New-Item -ItemType Directory -Path "runtime_logs" | Out-Null
}

$backendOut = "runtime_logs\backend_8001.out.log"
$backendErr = "runtime_logs\backend_8001.err.log"
$frontendOut = "runtime_logs\frontend_3000.out.log"
$frontendErr = "runtime_logs\frontend_3000.err.log"

"" | Set-Content $backendOut
"" | Set-Content $backendErr
"" | Set-Content $frontendOut
"" | Set-Content $frontendErr

$backendProc = Start-Process -FilePath "py" -ArgumentList "-3.11","-m","uvicorn","main:app","--host","0.0.0.0","--port","8001" -WorkingDirectory (Join-Path $repoRoot "backend") -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru
$frontendProc = Start-Process -FilePath "npm.cmd" -ArgumentList "start" -WorkingDirectory (Join-Path $repoRoot "frontend") -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru

Start-Sleep -Seconds 10

$backendListen = [bool](Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue)
$frontendListen = [bool](Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)

$backendHealthStatus = $null
$frontendHttpStatus = $null

try {
  $health = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -Method Get -TimeoutSec 5
  $backendHealthStatus = $health.status
} catch {}

try {
  $frontendHttpStatus = (Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 5).StatusCode
} catch {}

[ordered]@{
  backend_pid = $backendProc.Id
  frontend_pid = $frontendProc.Id
  backend_listening = $backendListen
  frontend_listening = $frontendListen
  backend_health_status = $backendHealthStatus
  frontend_http_status = $frontendHttpStatus
  backend_out_log = $backendOut
  backend_err_log = $backendErr
  frontend_out_log = $frontendOut
  frontend_err_log = $frontendErr
} | ConvertTo-Json -Depth 4
