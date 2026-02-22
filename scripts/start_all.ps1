$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (!(Test-Path "runtime_logs")) {
  New-Item -ItemType Directory -Path "runtime_logs" | Out-Null
}

function Stop-PortListener([int]$port) {
  $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
  foreach ($listener in $listeners) {
    try {
      Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    } catch {
      # Ignore stop errors for stale/system processes.
    }
  }
}

function Wait-Http([string]$url, [int]$timeoutSeconds = 120) {
  $deadline = (Get-Date).AddSeconds($timeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $true
      }
    } catch {
      # retry
    }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

function Wait-BackendHealth([string]$url, [int]$timeoutSeconds = 120) {
  $deadline = (Get-Date).AddSeconds($timeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $health = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 3
      if ($health.status -eq "healthy") {
        return $true
      }
    } catch {
      # retry
    }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

# Clean up any existing listeners on the project ports.
Stop-PortListener -port 3000
Stop-PortListener -port 8001
Stop-PortListener -port 8081
Start-Sleep -Seconds 1

$backendOut = "runtime_logs\backend_8001.out.log"
$backendErr = "runtime_logs\backend_8001.err.log"
$frontendOut = "runtime_logs\frontend_3000.out.log"
$frontendErr = "runtime_logs\frontend_3000.err.log"
$mobileOut = "runtime_logs\mobile_8081.out.log"
$mobileErr = "runtime_logs\mobile_8081.err.log"

"" | Set-Content $backendOut
"" | Set-Content $backendErr
"" | Set-Content $frontendOut
"" | Set-Content $frontendErr
"" | Set-Content $mobileOut
"" | Set-Content $mobileErr

$backendProc = Start-Process `
  -FilePath "py" `
  -ArgumentList "-3.11", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001" `
  -WorkingDirectory (Join-Path $repoRoot "backend") `
  -RedirectStandardOutput $backendOut `
  -RedirectStandardError $backendErr `
  -PassThru

$frontendProc = Start-Process `
  -FilePath "npm.cmd" `
  -ArgumentList "start" `
  -WorkingDirectory (Join-Path $repoRoot "frontend") `
  -RedirectStandardOutput $frontendOut `
  -RedirectStandardError $frontendErr `
  -PassThru

$mobileProc = Start-Process `
  -FilePath "flutter" `
  -ArgumentList "run", "-d", "web-server", "--web-hostname", "127.0.0.1", "--web-port", "8081", "--dart-define=AEGIS_API_BASE_URL=http://127.0.0.1:8001" `
  -WorkingDirectory (Join-Path $repoRoot "mobile_app") `
  -RedirectStandardOutput $mobileOut `
  -RedirectStandardError $mobileErr `
  -PassThru

$backendOk = Wait-BackendHealth -url "http://127.0.0.1:8001/health" -timeoutSeconds 90
$frontendOk = Wait-Http -url "http://127.0.0.1:3000" -timeoutSeconds 180
$mobileOk = Wait-Http -url "http://127.0.0.1:8081" -timeoutSeconds 240

[ordered]@{
  backend = [ordered]@{
    pid = $backendProc.Id
    url = "http://127.0.0.1:8001"
    healthy = $backendOk
    out_log = $backendOut
    err_log = $backendErr
  }
  frontend = [ordered]@{
    pid = $frontendProc.Id
    url = "http://127.0.0.1:3000"
    healthy = $frontendOk
    out_log = $frontendOut
    err_log = $frontendErr
  }
  mobile = [ordered]@{
    pid = $mobileProc.Id
    url = "http://127.0.0.1:8081"
    healthy = $mobileOk
    out_log = $mobileOut
    err_log = $mobileErr
  }
} | ConvertTo-Json -Depth 4
