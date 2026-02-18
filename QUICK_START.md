# Quick Start - AegisHub Telangana

## 1. Start backend

```bash
cd backend
py -3.11 -m pip install -r requirements.txt
py -3.11 init_db.py
py -3.11 -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## 2. Start frontend

```bash
cd frontend
npm install
npm start
```

## 3. Access

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8001`
- API docs: `http://localhost:8001/docs`

## 4. Demo login

- `admin / admin123`
- `responder / responder123`
- `viewer / viewer123`

## 5. Test SOS intake (authenticated)

1. Login via `POST /api/auth/login` and copy `access_token`.
2. Call:

```bash
curl -X POST "http://localhost:8001/api/sos/intake" ^
  -H "Authorization: Bearer <TOKEN>" ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Water entering homes, urgent rescue\",\"people\":8,\"longitude\":78.4867,\"latitude\":17.3850,\"place\":\"Hyderabad\",\"source\":\"mobile_app\"}"
```

## 6. Optional Gemini setup

In backend environment:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

If no Gemini key is set, rules-based triage remains active.
