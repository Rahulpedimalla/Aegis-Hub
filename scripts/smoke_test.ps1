$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$server = Start-Process -FilePath "py" -ArgumentList "-3.11", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001" -WorkingDirectory $backendDir -PassThru

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

  function Login([string]$username, [string]$password) {
    $body = @{ username = $username; password = $password } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/auth/login" -Method Post -ContentType "application/json" -Body $body
    return $resp.access_token
  }

  $adminToken = Login "admin" "admin123"
  $responderToken = Login "responder" "responder123"
  $viewerToken = Login "viewer" "viewer123"

  $responderHeaders = @{ Authorization = "Bearer $responderToken" }
  $viewerHeaders = @{ Authorization = "Bearer $viewerToken" }

  $viewerWriteBlocked = $false
  try {
    $viewerBody = @{
      text = "Need rescue due to rising flood water"
      people = 4
      longitude = 78.4867
      latitude = 17.3850
      place = "Hyderabad"
      source = "smoke_test"
    } | ConvertTo-Json
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/intake" -Method Post -Headers $viewerHeaders -ContentType "application/json" -Body $viewerBody | Out-Null
  } catch {
    $code = $null
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      $code = [int]$_.Exception.Response.StatusCode
    }
    if ($code -eq 403) {
      $viewerWriteBlocked = $true
    } else {
      throw
    }
  }

  $intakeBody = @{
    text = "Flood water entered homes, children trapped on first floor, urgent boat rescue needed"
    people = 12
    longitude = 79.5941
    latitude = 17.9689
    place = "Warangal Urban"
    source = "smoke_test"
  } | ConvertTo-Json

  $intake = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/intake" -Method Post -Headers $responderHeaders -ContentType "application/json" -Body $intakeBody
  $sosId = $intake.sos_id

  $smart = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/smart-assignment?sos_id=$sosId" -Method Get -Headers $responderHeaders
  $orgId = $smart.recommended_assignment.organization.id
  $staffId = $smart.recommended_assignment.staff.id
  $divisionId = $smart.recommended_assignment.division.id

  if (-not $orgId) {
    $orgId = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/organizations/" -Method Get -Headers $responderHeaders)[0].id
  }

  $orgBefore = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/organizations/$orgId" -Method Get -Headers $responderHeaders).current_load
  $divBefore = $null
  if ($divisionId) {
    $divBefore = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/divisions/$divisionId" -Method Get -Headers $responderHeaders).current_load
  }
  $staffBefore = $null
  if ($staffId) {
    $staffBefore = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/staff/$staffId" -Method Get -Headers $responderHeaders).availability
  }

  $assignBody = @{
    sos_id = $sosId
    organization_id = $orgId
    staff_id = $staffId
    division_id = $divisionId
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/assign-emergency" -Method Post -Headers $responderHeaders -ContentType "application/json" -Body $assignBody | Out-Null

  $orgAfterAssign = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/organizations/$orgId" -Method Get -Headers $responderHeaders).current_load
  $divAfterAssign = $null
  if ($divisionId) {
    $divAfterAssign = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/divisions/$divisionId" -Method Get -Headers $responderHeaders).current_load
  }
  $staffAfterAssign = $null
  if ($staffId) {
    $staffAfterAssign = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/staff/$staffId" -Method Get -Headers $responderHeaders).availability
  }

  $acceptBody = @{
    sos_id = $sosId
    organization_id = $orgId
    estimated_completion = (Get-Date).ToUniversalTime().AddHours(1).ToString("o")
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/accept-assignment" -Method Post -Headers $responderHeaders -ContentType "application/json" -Body $acceptBody | Out-Null

  $statusAfterAccept = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/$sosId" -Method Get -Headers $responderHeaders).status

  $completeBody = @{
    sos_id = $sosId
    resolution_notes = "Smoke test completed successfully"
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/emergency/complete-emergency" -Method Post -Headers $responderHeaders -ContentType "application/json" -Body $completeBody | Out-Null

  $orgAfterComplete = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/organizations/$orgId" -Method Get -Headers $responderHeaders).current_load
  $divAfterComplete = $null
  if ($divisionId) {
    $divAfterComplete = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/divisions/$divisionId" -Method Get -Headers $responderHeaders).current_load
  }
  $staffAfterComplete = $null
  if ($staffId) {
    $staffAfterComplete = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/staff/$staffId" -Method Get -Headers $responderHeaders).availability
  }

  $sosFinal = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/sos/$sosId" -Method Get -Headers $responderHeaders

  [ordered]@{
    health = "ok"
    auth = [ordered]@{
      admin_login = [bool]$adminToken
      responder_login = [bool]$responderToken
      viewer_login = [bool]$viewerToken
      viewer_write_blocked = $viewerWriteBlocked
    }
    sos = [ordered]@{
      id = $sosId
      triage_source = $intake.triage.source
      category = $intake.triage.category
      priority = $intake.triage.priority
    }
    assignment = [ordered]@{
      organization_id = $orgId
      division_id = $divisionId
      staff_id = $staffId
      org_load_before = $orgBefore
      org_load_after_assign = $orgAfterAssign
      org_load_after_complete = $orgAfterComplete
      division_load_before = $divBefore
      division_load_after_assign = $divAfterAssign
      division_load_after_complete = $divAfterComplete
      staff_before = $staffBefore
      staff_after_assign = $staffAfterAssign
      staff_after_complete = $staffAfterComplete
    }
    lifecycle = [ordered]@{
      status_after_accept = $statusAfterAccept
      final_status = $sosFinal.status
      actual_completion_present = [bool]$sosFinal.actual_completion
    }
    ai_assignment_context = $smart.ai_assignment_context
  } | ConvertTo-Json -Depth 8
}
finally {
  if ($server -and !$server.HasExited) {
    Stop-Process -Id $server.Id -Force
  }
}
