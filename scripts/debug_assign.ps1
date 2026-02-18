$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"

& py -3.11 (Join-Path $backendDir "init_db.py") | Out-Null

$existing = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
  $existing.OwningProcess | Sort-Object -Unique | ForEach-Object {
    Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
  }
}

$outLog = Join-Path $repoRoot "scripts\debug_backend_out.log"
$errLog = Join-Path $repoRoot "scripts\debug_backend_err.log"
if (Test-Path $outLog) { Remove-Item $outLog -Force }
if (Test-Path $errLog) { Remove-Item $errLog -Force }

$server = Start-Process -FilePath "py" -ArgumentList "-3.11", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001" -WorkingDirectory $backendDir -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru

try {
  $healthy = $false
  for ($i = 0; $i -lt 40; $i++) {
    try {
      $h = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -Method Get -TimeoutSec 2
      if ($h.status -eq "healthy") { $healthy = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
  }
  if (-not $healthy) { throw "Backend did not become healthy" }

  $loginBody = @{ role = "responder"; username = "responder"; password = "responder123" } | ConvertTo-Json
  $login = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
  $headers = @{ Authorization = "Bearer $($login.access_token)" }

  $intakeBody = @{
    text = "Flood water entered homes, children trapped on first floor, urgent boat rescue needed"
    people = 12
    longitude = 79.5941
    latitude = 17.9689
    place = "Warangal Urban"
    source = "debug"
  } | ConvertTo-Json
  $intake = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/intake" -Method Post -Headers $headers -ContentType "application/json" -Body $intakeBody
  $sosId = $intake.sos_id

  $smart = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/smart-assignment?sos_id=$sosId" -Method Get -Headers $headers
  "SMART_RECOMMENDED:"
  ($smart.recommended_assignment | ConvertTo-Json -Depth 6)
  $assignBody = @{
    sos_id = $sosId
    organization_id = $smart.recommended_assignment.organization.id
    staff_id = $smart.recommended_assignment.staff.id
    division_id = $smart.recommended_assignment.division.id
  } | ConvertTo-Json
  "ASSIGN_BODY:"
  $assignBody

  try {
    $assign = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/assign-emergency" -Method Post -Headers $headers -ContentType "application/json" -Body $assignBody
    "ASSIGN_OK"
    $assign | ConvertTo-Json -Depth 5
  } catch {
    "ASSIGN_FAILED"
    $_.Exception.Message
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
      $_.ErrorDetails.Message
    }
    if ($_.Exception.Response) {
      $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
      $sr.ReadToEnd()
    } else {
      $_.Exception.Message
    }
  }
}
finally {
  if ($server -and !$server.HasExited) {
    Stop-Process -Id $server.Id -Force
  }
  "=== STDERR ==="
  if (Test-Path $errLog) { Get-Content $errLog }
  "=== STDOUT ==="
  if (Test-Path $outLog) { Get-Content $outLog }
}
