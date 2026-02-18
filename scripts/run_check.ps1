$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

$backend = Start-Process -FilePath "py" -ArgumentList "-3.11", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001" -WorkingDirectory $backendDir -PassThru
$frontend = Start-Process -FilePath "npm.cmd" -ArgumentList "start" -WorkingDirectory $frontendDir -PassThru

try {
  $backendOk = $false
  for ($i = 0; $i -lt 40; $i++) {
    try {
      $h = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -Method Get -TimeoutSec 2
      if ($h.status -eq "healthy") {
        $backendOk = $true
        break
      }
    } catch {
      # retry
    }
    Start-Sleep -Milliseconds 500
  }

  $frontendOk = $false
  for ($i = 0; $i -lt 120; $i++) {
    try {
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -eq 200) {
        $frontendOk = $true
        break
      }
    } catch {
      # retry
    }
    Start-Sleep -Milliseconds 500
  }

  [ordered]@{
    backend_ok = $backendOk
    frontend_ok = $frontendOk
  } | ConvertTo-Json
}
finally {
  if ($frontend -and !$frontend.HasExited) {
    Stop-Process -Id $frontend.Id -Force
  }
  if ($backend -and !$backend.HasExited) {
    Stop-Process -Id $backend.Id -Force
  }
}
