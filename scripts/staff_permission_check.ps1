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

function Login([string]$role, [string]$username, [string]$password) {
  $body = @{ role = $role; username = $username; password = $password } | ConvertTo-Json
  $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/auth/login" -Method Post -ContentType "application/json" -Body $body
  return $resp.access_token
}

function UsernameFromStaffName([string]$name) {
  $u = $name.ToLower()
  $u = $u -replace '[^a-z0-9]+', '.'
  $u = $u.Trim('.')
  return $u
}

function Wait-Healthy {
  for ($i = 0; $i -lt 40; $i++) {
    try {
      $h = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -Method Get -TimeoutSec 2
      if ($h.status -eq "healthy") { return $true }
    } catch {}
    Start-Sleep -Milliseconds 500
  }
  return $false
}

try {
  if (-not (Wait-Healthy)) { throw "Backend did not become healthy in time." }

  $adminHeaders = @{ Authorization = "Bearer $(Login 'admin' 'admin' 'admin123')" }

  $allResponderUsers = @(
    "harish.rao",
    "dr.sneha.reddy",
    "kiran.kumar",
    "madhavi.ch"
  )

  # ---------- Ticket A: accept + complete checks ----------
  $ticketA = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/" -Method Post -Headers $adminHeaders -ContentType "application/json" -Body (@{
    external_id = "STAFF-CHECK-A-$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
    people = 7
    longitude = 79.5941
    latitude = 17.9689
    text = "Staff permission check A"
    place = "Warangal Urban"
    category = "Flood Rescue"
  } | ConvertTo-Json)
  $sosA = $ticketA.id

  $smartA = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/smart-assignment?sos_id=$sosA" -Method Get -Headers $adminHeaders
  $staffAId = $smartA.recommended_assignment.staff.id
  $staffAObj = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/staff/$staffAId" -Method Get -Headers $adminHeaders
  $assignedUserA = UsernameFromStaffName $staffAObj.name
  $otherUserA = ($allResponderUsers | Where-Object { $_ -ne $assignedUserA })[0]

  $assignedHeadersA = @{ Authorization = "Bearer $(Login 'responder' $assignedUserA 'responder123')" }
  $otherHeadersA = @{ Authorization = "Bearer $(Login 'responder' $otherUserA 'responder123')" }

  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/assign-emergency" -Method Post -Headers $adminHeaders -ContentType "application/json" -Body (@{
    sos_id = $sosA
    organization_id = $smartA.recommended_assignment.organization.id
    staff_id = $staffAId
    division_id = $smartA.recommended_assignment.division.id
  } | ConvertTo-Json) | Out-Null

  $acceptBodyA = @{
    sos_id = $sosA
    organization_id = $smartA.recommended_assignment.organization.id
    estimated_completion = (Get-Date).ToUniversalTime().AddHours(1).ToString("o")
  } | ConvertTo-Json

  $otherAcceptA = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/accept-assignment" -Method Post -Headers $otherHeadersA -ContentType "application/json" -Body $acceptBodyA
  }
  $assignedAcceptA = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/accept-assignment" -Method Post -Headers $assignedHeadersA -ContentType "application/json" -Body $acceptBodyA
  }

  $completeBodyA = @{ sos_id = $sosA; resolution_notes = "staff check complete A" } | ConvertTo-Json
  $otherCompleteA = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/complete-emergency" -Method Post -Headers $otherHeadersA -ContentType "application/json" -Body $completeBodyA
  }
  $assignedCompleteA = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/complete-emergency" -Method Post -Headers $assignedHeadersA -ContentType "application/json" -Body $completeBodyA
  }

  # ---------- Ticket B: reject checks ----------
  $ticketB = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/" -Method Post -Headers $adminHeaders -ContentType "application/json" -Body (@{
    external_id = "STAFF-CHECK-B-$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
    people = 4
    longitude = 79.5941
    latitude = 17.9689
    text = "Staff permission check B"
    place = "Warangal Urban"
    category = "Flood Rescue"
  } | ConvertTo-Json)
  $sosB = $ticketB.id

  $smartB = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/smart-assignment?sos_id=$sosB" -Method Get -Headers $adminHeaders
  $staffBId = $smartB.recommended_assignment.staff.id
  $staffBObj = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/staff/$staffBId" -Method Get -Headers $adminHeaders
  $assignedUserB = UsernameFromStaffName $staffBObj.name
  $otherUserB = ($allResponderUsers | Where-Object { $_ -ne $assignedUserB })[0]

  $assignedHeadersB = @{ Authorization = "Bearer $(Login 'responder' $assignedUserB 'responder123')" }
  $otherHeadersB = @{ Authorization = "Bearer $(Login 'responder' $otherUserB 'responder123')" }

  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/assign-emergency" -Method Post -Headers $adminHeaders -ContentType "application/json" -Body (@{
    sos_id = $sosB
    organization_id = $smartB.recommended_assignment.organization.id
    staff_id = $staffBId
    division_id = $smartB.recommended_assignment.division.id
  } | ConvertTo-Json) | Out-Null

  $rejectBodyB = @{
    sos_id = $sosB
    organization_id = $smartB.recommended_assignment.organization.id
    reason = "staff check reject B"
  } | ConvertTo-Json
  $otherRejectB = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/reject-assignment" -Method Post -Headers $otherHeadersB -ContentType "application/json" -Body $rejectBodyB
  }
  $assignedRejectB = Get-StatusCode {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/reject-assignment" -Method Post -Headers $assignedHeadersB -ContentType "application/json" -Body $rejectBodyB
  }

  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/$sosA" -Method Delete -Headers $adminHeaders | Out-Null
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/$sosB" -Method Delete -Headers $adminHeaders | Out-Null

  [ordered]@{
    ticket_a_assigned_staff_user = $assignedUserA
    ticket_b_assigned_staff_user = $assignedUserB
    accept_other_staff_status = $otherAcceptA
    accept_assigned_staff_status = $assignedAcceptA
    complete_other_staff_status = $otherCompleteA
    complete_assigned_staff_status = $assignedCompleteA
    reject_other_staff_status = $otherRejectB
    reject_assigned_staff_status = $assignedRejectB
  } | ConvertTo-Json -Depth 4
}
finally {
  if ($server -and !$server.HasExited) {
    Stop-Process -Id $server.Id -Force
  }
}
