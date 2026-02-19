# Aegis Hub Mobile App

Production-focused Flutter client for citizen-side emergency intake.

## Implemented

- Clean Architecture style feature modules with Riverpod state management.
- Runtime-configurable backend endpoint with fallback chain:
  1. secure override in `flutter_secure_storage`
  2. `--dart-define=AEGIS_API_BASE_URL=...`
  3. `assets/config/runtime_config.json`
- SOS flow with one-tap voice capture start, GPS + device metadata, raw transcript capture, and resilient submission.
- Normal ticket flow with text + multi-image + video + optional voice note.
- Provider-agnostic voice layer (`STT`, `TTS`, realtime voice) with selectable provider router.
- Local offline queue for ticket retry.
- Post-ticket AI chat entry state.

## Folder Highlights

- `lib/features/sos/` SOS controller and emergency-first home UI.
- `lib/features/tickets/` normal ticket creation and payload models.
- `lib/features/chat/` follow-up conversational flow.
- `lib/features/voice/` STT/TTS/realtime abstraction and provider router.
- `lib/core/network/` multipart upload and API client.
- `lib/core/storage/` durable local queue.
- `assets/config/runtime_config.json` runtime endpoint/provider config.

## Payload Contract

The app sends multipart form data:

- `metadata` JSON part containing:
  - `text`
  - `voice_transcript` (raw transcript object)
  - `latitude`, `longitude`, `timestamp`
  - `device_info`
  - `ticket_type` (`SOS` or `Normal`)
  - media checksums/sizes and idempotency metadata
- file parts:
  - `images[]`
  - `videos[]`
  - `audio_file` (optional)

## Provider Integration

Adapters currently include integration points for:

- STT: `deepgram`, `elevenlabs`, `cartesia`
- TTS: `cartesia`, `elevenlabs`
- Realtime agent: `openai_realtime`

Wire API keys and HTTP integration in:

- `lib/features/voice/data/providers/`

## Run

1. Install Flutter SDK and toolchains.
2. If platform folders are missing, run `flutter create .` in `mobile_app/`.
3. From `mobile_app/`:
   - `flutter pub get`
   - `flutter run --dart-define=AEGIS_API_BASE_URL=http://<host>:8001`
   - `flutter test`

For Android emulator against local backend, default config uses `http://10.0.2.2:8001`.

Detailed platform permission setup is in `SETUP.md`.
