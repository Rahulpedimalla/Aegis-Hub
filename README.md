# AegisHub Telangana Disaster Response Platform

End-to-end emergency response platform for Telangana with AI triage, smart ticket assignment, role-based dashboards, and geospatial flood monitoring.

## Runbook

For complete setup and execution of backend + frontend + mobile app with AI pipeline, see `IMPLEMENTATION.md`.

## What this project includes

- FastAPI backend with authenticated APIs for SOS lifecycle and operational data.
- React frontend dashboard for incident monitoring and response coordination.
- SQLite operational database with seeded Telangana organizations, divisions, staff, shelters, hospitals, and resource centers.
- AI-assisted ticket triage and assignment (Gemini-enabled with safe rule fallback).
- Workload-aware assignment tracking across organization, division, and responder.

## Core features implemented

### 1. Smart ticket assignment by AI

- Incoming SOS requests are triaged by `backend/services/triage_service.py`.
- Gemini integration is available in `backend/services/gemini_service.py`.
- If Gemini is unavailable or returns invalid output, deterministic rules are used.
- Assignment engine (`backend/services/assignment_service.py`) scores:
  - distance,
  - required skills,
  - division type fit,
  - capacity/load.

### 2. Proper DB updates on assignment and completion

- Assignment lifecycle updates are handled in `backend/services/workload_service.py`.
- On assign/reassign:
  - organization/division `current_load` increments/decrements correctly,
  - staff availability changes to `Busy`/`Available`.
- On complete/cancel:
  - workload is released,
  - ticket completion timestamp is stored.

### 3. Role-based access and dashboards

- Roles: `admin`, `responder`, `viewer`.
- API access control via `require_roles(...)` in `backend/routes/auth_routes.py`.
- Frontend route visibility and edit permissions are role-aware.
- Professional landing page + login flow included.

## Demo credentials

- `admin / admin123`
- `responder / responder123`
- `viewer / viewer123`

## Telangana setup

Seed data is Telangana-focused:

- Telangana State Disaster Management Authority
- Telangana Fire and Emergency Services
- Hyderabad/Warangal/Nizamabad aligned facilities
- Telangana division routing and region statistics

Database initializer:

- `backend/init_db.py`

## Project structure

```
backend/
  main.py
  database.py
  init_db.py
  routes/
  services/
frontend/
  src/
scripts/
  smoke_test.ps1
```

## Run locally

### Backend

```bash
cd backend
py -3.11 -m pip install -r requirements.txt
py -3.11 init_db.py
py -3.11 -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```bash
cd frontend
npm install
npm start
```

URLs:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8001`
- Swagger: `http://localhost:8001/docs`

## Gemini configuration

Set in backend environment (`.env` or runtime env):

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Without `GEMINI_API_KEY`, the system automatically uses rule-based triage.

## Verified execution

Smoke test script:

- `scripts/smoke_test.ps1`

Validated flow:

- login as all roles,
- viewer write denial,
- responder intake,
- smart assignment,
- assign -> accept -> complete,
- workload increments/decrements and staff availability transitions.

## Next phase

Current system is API + dashboard complete. Mobile citizen application intake can now be built on top of:

- `POST /api/sos/intake`
- assignment and response endpoints under `/api/emergency`

Additional mobile-optimized endpoints are now available:

- `POST /api/mobile/tickets` (multipart `metadata` + `images[]` + `videos[]` + `audio_file`)
- `POST /api/mobile/chat/{chat_session_id}/messages`

## AI-powered mobile incident pipeline

The backend now processes mobile incidents end-to-end before dispatching to ticket creation:

- Multi-modal normalization (Voice/Image/Video/Text/Emergency SOS category detection).
- AI analysis across modalities (transcript fallback, media insight, incident typing, summary).
- Weather verification for weather-related incidents (Open-Meteo + cache fallback).
- Nearby-ticket density checks and fraud/spam risk scoring.
- Priority score + queue lane assignment (`p0`..`p3`).
- Idempotent dispatch with retry and audit logs.

Supporting endpoints:

- `POST /api/mobile/tickets` -> analyze + verify + priority + dispatch.
- `POST /api/mobile/ticket-creation-endpoint` -> target ticket creation endpoint (idempotent).
- `POST /api/mobile/dispatch/retry-pending` -> retry queued/failed dispatches.
- `GET /api/mobile/incidents/{incident_id}` -> incident processing and dispatch status.
- `POST /api/mobile/ai/voice-agent` -> Gemini-powered voice/text follow-up response.

Example ingest call:

```bash
curl -X POST "http://localhost:8001/api/mobile/tickets" \
  -F "metadata={\"ticket_type\":\"SOS\",\"text\":\"Water rising rapidly near bridge\",\"latitude\":17.3850,\"longitude\":78.4867,\"timestamp\":\"2026-02-19T18:25:14Z\",\"ticket_id_client\":\"APP-DEMO-001\",\"metadata\":{\"idempotency_key\":\"APP-DEMO-001\"}}" \
  -F "images=@sample.jpg" \
  -F "audio_file=@sample.m4a"
```
