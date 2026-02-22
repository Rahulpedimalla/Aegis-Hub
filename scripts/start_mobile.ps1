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
      # ignore
    }
  }
}

Stop-PortListener -port 8081
Start-Sleep -Seconds 1

$mobileOut = "runtime_logs\mobile_8081.out.log"
$mobileErr = "runtime_logs\mobile_8081.err.log"
"" | Set-Content $mobileOut
"" | Set-Content $mobileErr

$mobileProc = Start-Process `
  -FilePath "flutter" `
  -ArgumentList "run", "-d", "web-server", "--web-hostname", "127.0.0.1", "--web-port", "8081", "--dart-define=AEGIS_API_BASE_URL=http://127.0.0.1:8001" `
  -WorkingDirectory (Join-Path $repoRoot "mobile_app") `
  -RedirectStandardOutput $mobileOut `
  -RedirectStandardError $mobileErr `
  -PassThru

[ordered]@{
  pid = $mobileProc.Id
  url = "http://127.0.0.1:8081"
  out_log = $mobileOut
  err_log = $mobileErr
} | ConvertTo-Json -Depth 3
