$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"

# Ensure seed users/credentials are up to date for role checks.
& py -3.11 (Join-Path $backendDir "init_db.py") | Out-Null

# Stop any existing backend listener on 8001 to avoid false-positive checks.
$existing = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
  $existing.OwningProcess | Sort-Object -Unique | ForEach-Object {
    Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
  }
}

$server = Start-Process -FilePath "py" -ArgumentList "-3.11", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001" -WorkingDirectory $backendDir -PassThru

function Get-StatusCode {
  param([scriptblock]$Action)
  try {
    & $Action | Out-Null
    return 200
  } catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      return [int]$_.Exception.Response.StatusCode
    }
    throw
  }
}

try {
  $healthy = $false
  for ($i = 0; $i -lt 40; $i++) {
    try {
      $h = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -Method Get -TimeoutSec 2
      if ($h.status -eq "healthy") {
        $healthy = $true
        break
      }
    } catch {
      # wait and retry
    }
    Start-Sleep -Milliseconds 500
  }
  if (-not $healthy) {
    throw "Backend did not become healthy in time."
  }

  function Login([string]$role, [string]$username, [string]$password) {
    $body = @{ role = $role; username = $username; password = $password } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/auth/login" -Method Post -ContentType "application/json" -Body $body
    return $resp.access_token
  }

  $adminToken = Login "admin" "admin" "admin123"
  $responderToken = Login "responder" "responder" "responder123"
  $viewerToken = Login "viewer" "viewer" "viewer123"
  $staffResponderToken = Login "responder" "harish.rao" "responder123"

  $adminHeaders = @{ Authorization = "Bearer $adminToken" }
  $responderHeaders = @{ Authorization = "Bearer $responderToken" }
  $viewerHeaders = @{ Authorization = "Bearer $viewerToken" }

  $roleMismatchCode = Get-StatusCode {
    $bad = @{ role = "viewer"; username = "admin"; password = "admin123" } | ConvertTo-Json
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/auth/login" -Method Post -ContentType "application/json" -Body $bad
  }

  # Admin create ticket
  $ticketPayload = @{
    external_id = "ADMIN-RBAC-$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
    people = 5
    longitude = 78.4867
    latitude = 17.3850
    text = "RBAC validation ticket"
    place = "Hyderabad"
    category = "Flood Rescue"
  } | ConvertTo-Json
  $createdTicket = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/" -Method Post -Headers $adminHeaders -ContentType "application/json" -Body $ticketPayload
  $sosId = $createdTicket.id

  # Assign as admin
  $smart = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/smart-assignment?sos_id=$sosId" -Method Get -Headers $adminHeaders
  $assignBody = @{
    sos_id = $sosId
    organization_id = $smart.recommended_assignment.organization.id
    staff_id = $smart.recommended_assignment.staff.id
    division_id = $smart.recommended_assignment.division.id
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/assign-emergency" -Method Post -Headers $adminHeaders -ContentType "application/json" -Body $assignBody | Out-Null

  # Admin must be blocked from accept/reject
  $acceptBody = @{
    sos_id = $sosId
    organization_id = $smart.recommended_assignment.organization.id
    estimated_completion = (Get-Date).ToUniversalTime().AddHours(1).ToString("o")
  } | ConvertTo-Json
  $adminAcceptCode = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/accept-assignment" -Method Post -Headers $adminHeaders -ContentType "application/json" -Body $acceptBody
  }
  $adminRejectCode = Get-StatusCode {
    $rejectBody = @{
      sos_id = $sosId
      organization_id = $smart.recommended_assignment.organization.id
      reason = "RBAC test"
    } | ConvertTo-Json
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/reject-assignment" -Method Post -Headers $adminHeaders -ContentType "application/json" -Body $rejectBody
  }

  # Responder can accept
  $responderAcceptCode = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/accept-assignment" -Method Post -Headers $responderHeaders -ContentType "application/json" -Body $acceptBody
  }

  # Flood endpoints admin-only
  $adminFloodCode = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/flood-detection/satellite-status" -Method Get -Headers $adminHeaders
  }
  $responderFloodCode = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/flood-detection/satellite-status" -Method Get -Headers $responderHeaders
  }
  $viewerFloodCode = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/flood-detection/satellite-status" -Method Get -Headers $viewerHeaders
  }

  # Map data should be available for responder/viewer
  $responderMapCode = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/map" -Method Get -Headers $responderHeaders
  }
  $viewerMapCode = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/map" -Method Get -Headers $viewerHeaders
  }

  # Cleanup ticket as admin
  $adminDeleteCode = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/$sosId" -Method Delete -Headers $adminHeaders
  }

  [ordered]@{
    login = [ordered]@{
      admin = [bool]$adminToken
      responder = [bool]$responderToken
      viewer = [bool]$viewerToken
      staff_responder = [bool]$staffResponderToken
      role_mismatch_status = $roleMismatchCode
    }
    emergency_response = [ordered]@{
      admin_accept_status = $adminAcceptCode
      admin_reject_status = $adminRejectCode
      responder_accept_status = $responderAcceptCode
    }
    geospatial_access = [ordered]@{
      admin_flood_status = $adminFloodCode
      responder_flood_status = $responderFloodCode
      viewer_flood_status = $viewerFloodCode
      responder_map_status = $responderMapCode
      viewer_map_status = $viewerMapCode
    }
    ticket_admin_actions = [ordered]@{
      created_ticket_id = $sosId
      delete_status = $adminDeleteCode
    }
  } | ConvertTo-Json -Depth 6
}
finally {
  if ($server -and !$server.HasExited) {
    Stop-Process -Id $server.Id -Force
  }
}
