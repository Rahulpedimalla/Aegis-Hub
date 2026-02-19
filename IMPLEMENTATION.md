# Aegis Hub Implementation Runbook

This document is the source of truth for running the full Aegis Hub stack locally:

- FastAPI backend (`backend/`)
- React dashboard (`frontend/`)
- Flutter mobile app (`mobile_app/`) in web mode (Chrome)
- AI pipeline (Gemini-powered ingestion, verification, prioritization, dispatch, and chat/voice agent)

## 1. Prerequisites

Install the following:

- Python 3.11+ (project has been tested with 3.13)
- Node.js 18+ and npm
- Flutter SDK 3.41+ and Chrome browser

Optional but recommended:

- PowerShell 7+ (commands below also work in Windows PowerShell)

## 2. Security First

Use a valid Gemini API key in environment variables or `backend/.env`.

Do not hardcode secrets in source code.

If any key was shared in plaintext, rotate/revoke it and use a new key.

## 3. Project Layout

```txt
backend/      FastAPI APIs, AI pipeline, DB models, routing
frontend/     React operations dashboard
mobile_app/   Flutter mobile client (web/android/ios capable)
scripts/      Utility scripts and smoke checks
```

## 4. Backend Setup (AI Pipeline + APIs)

From repo root:

```powershell
cd backend
..\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create backend env file:

```powershell
Copy-Item env_example.txt .env -Force
```

Edit `backend/.env` and set at minimum:

```env
GEMINI_API_KEY=your_new_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Optional dispatch settings:

```env
MOBILE_TICKET_CREATION_ENDPOINT=
MOBILE_TICKET_ENDPOINT_AUTH_TOKEN=
MOBILE_DISPATCH_MAX_ATTEMPTS=6
MOBILE_DISPATCH_INITIAL_BACKOFF_SECONDS=1.0
```

Initialize DB (first run only):

```powershell
..\venv\Scripts\python.exe init_db.py
```

Run backend:

```powershell
..\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Verify health:

- `http://localhost:8001/health`
- `http://localhost:8001/docs`

## 5. Frontend Setup (Dashboard)

In a new terminal:

```powershell
cd frontend
npm install
npm start
```

Dashboard runs at:

- `http://localhost:3000`

## 6. Mobile App Setup (Flutter Web)

In a new terminal:

```powershell
cd mobile_app
..\flutter\bin\flutter.bat pub get
..\flutter\bin\flutter.bat analyze
```

Run on Chrome:

```powershell
..\flutter\bin\flutter.bat run -d chrome --web-port 8080 --dart-define=AEGIS_API_BASE_URL=http://localhost:8001
```

Notes:

- If Flutter is in your global `PATH`, use `flutter` directly.
- For browser mic/location, allow permissions in Chrome.

## 7. End-to-End Validation Flow

1. Start backend (`8001`), frontend (`3000`), and mobile web (`8080`).
2. In mobile app:
   - Tap SOS (voice capture starts)
   - Submit SOS
   - Open Chat and test text/voice follow-up
3. Confirm backend pipeline:
   - Ticket is created/dispatched
   - AI categorization/priority is returned
   - Chat/voice agent replies are AI-generated

## 8. API Validation (Manual)

### 8.1 Mobile ticket ingest

```bash
curl -X POST "http://localhost:8001/api/mobile/tickets" \
  -F "metadata={\"ticket_type\":\"SOS\",\"text\":\"Flood water rising near bridge\",\"latitude\":17.3850,\"longitude\":78.4867,\"timestamp\":\"2026-02-19T18:25:14Z\",\"ticket_id_client\":\"APP-DEMO-001\",\"metadata\":{\"idempotency_key\":\"APP-DEMO-001\"}}"
```

### 8.2 Incident status

```bash
curl "http://localhost:8001/api/mobile/incidents/APP-DEMO-001"
```

### 8.3 AI text chat

```bash
curl -X POST "http://localhost:8001/api/mobile/chat/<CHAT_SESSION_ID>/messages" \
  -H "Content-Type: application/json" \
  -d "{\"role\":\"user\",\"text\":\"We have elderly with us and water is rising\"}"
```

### 8.4 AI voice agent (text hint fallback)

```bash
curl -X POST "http://localhost:8001/api/mobile/ai/voice-agent" \
  -F "chat_session_id=<CHAT_SESSION_ID>" \
  -F "text_hint=Water is rising and evacuation is difficult"
```

## 9. Implemented AI-Powered Endpoints

- `POST /api/mobile/tickets`
- `POST /api/mobile/chat/{chat_session_id}/messages`
- `POST /api/mobile/ai/voice-agent`
- `GET /api/mobile/incidents/{incident_id}`
- `POST /api/mobile/dispatch/retry-pending`
- `POST /api/mobile/ticket-creation-endpoint`

## 10. Troubleshooting

### Flutter not found

Use local SDK path:

```powershell
..\flutter\bin\flutter.bat --version
```

### SOS button not working on web

- Allow microphone and location in Chrome.
- Confirm `flutter analyze` passes.
- Ensure backend is reachable from browser (`http://localhost:8001/health`).

### Ticket stuck as `Queued`

- Run retry endpoint:

```bash
curl -X POST "http://localhost:8001/api/mobile/dispatch/retry-pending"
```

- Check backend logs and `MOBILE_TICKET_CREATION_ENDPOINT` config.

### Gemini responses missing

- Verify `GEMINI_API_KEY` in `backend/.env`.
- Restart backend after env change.

## 11. Recommended Local Startup Order

1. Backend
2. Frontend
3. Mobile app
4. Run SOS + chat test
