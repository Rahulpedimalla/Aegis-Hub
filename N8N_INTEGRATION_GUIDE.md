# n8n Integration Guide (Telangana)

## Goal

Push incidents from n8n into AegisHub so the backend triages and routes tickets automatically.

## Authentication

1. Login:
   - `POST /api/auth/login`
2. Use returned bearer token on downstream calls.

## Intake endpoint

- URL: `POST http://localhost:8001/api/sos/intake`
- Headers:
  - `Authorization: Bearer <TOKEN>`
  - `Content-Type: application/json`

## Payload

```json
{
  "external_id": "n8n_emergency_001",
  "text": "Heavy rainfall and rising water level. Families trapped.",
  "voice_transcript": null,
  "people": 12,
  "longitude": 79.5941,
  "latitude": 17.9689,
  "place": "Warangal Urban, Telangana",
  "category_hint": "Flood Rescue",
  "source": "n8n_workflow",
  "contact_phone": "+91-90000-00000"
}
```

## Coordinate examples (Telangana)

- Hyderabad: `78.4867`, `17.3850`
- Warangal: `79.5941`, `17.9689`
- Nizamabad: `78.0941`, `18.6725`

## Expected response

The intake API returns:

- `sos_id`
- triage result (`category`, `priority`, `division_type`, `source`)
- recommended org/staff/division IDs

## Suggested n8n flow

1. Trigger node (Webhook/Schedule/External source).
2. Function node to normalize payload.
3. HTTP Request node to `/api/auth/login`.
4. HTTP Request node to `/api/sos/intake`.
5. Optional branch for notifications/escalation.

## Error handling recommendations

- Retry transient HTTP 5xx with exponential backoff.
- Route 4xx payload errors to a dead-letter queue.
- Store `external_id` and `sos_id` mapping for traceability.
