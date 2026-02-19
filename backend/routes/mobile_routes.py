import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import (
    MobileDispatchAttempt,
    MobileIncident,
    SOSRequest,
    TicketCreationRecord,
    get_db,
)
from services.gemini_service import gemini_chat_followup_response, gemini_transcribe_audio
from services.mobile_ai_pipeline_service import build_ai_incident_bundle
from services.mobile_dispatch_service import dispatch_ticket_with_retry

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "static" / "mobile_uploads"
IN_MEMORY_CHAT: Dict[str, List[Dict[str, str]]] = {}


class MobileChatMessage(BaseModel):
    role: str
    text: str
    timestamp: Optional[str] = None


def _safe_file_name(value: Optional[str]) -> str:
    name = Path(value or "").name.strip()
    return name or f"upload-{uuid.uuid4().hex[:8]}"


async def _save_upload(incident_ref: str, bucket: str, file: UploadFile) -> Dict[str, Any]:
    ticket_dir = UPLOAD_DIR / incident_ref / bucket
    ticket_dir.mkdir(parents=True, exist_ok=True)
    file_name = _safe_file_name(file.filename)
    destination = ticket_dir / file_name
    content = await file.read()
    destination.write_bytes(content)
    return {
        "file_name": file_name,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "relative_path": str(destination.relative_to(UPLOAD_DIR.parent)),
        "disk_path": str(destination.resolve()),
    }


def _extract_idempotency_key(metadata: Dict[str, Any]) -> str:
    nested = metadata.get("metadata") or {}
    if not isinstance(nested, dict):
        nested = {}
    candidates = [
        nested.get("idempotency_key"),
        metadata.get("idempotency_key"),
        metadata.get("ticket_id_client"),
        metadata.get("external_id"),
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value
    return f"idem-{uuid.uuid4().hex}"


def _resolve_dispatch_endpoint(request: Request) -> str:
    configured = str(os.getenv("MOBILE_TICKET_CREATION_ENDPOINT", "")).strip()
    if configured:
        return configured
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/mobile/ticket-creation-endpoint"


def _build_internal_ticket_creation_endpoint(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/mobile/ticket-creation-endpoint"


def _is_internal_dispatch_endpoint(request: Request, endpoint: str) -> bool:
    expected = _build_internal_ticket_creation_endpoint(request).rstrip("/")
    return endpoint.rstrip("/") == expected


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _fallback_follow_up_reply(text: str) -> str:
    lower = text.lower()
    if "injur" in lower or "bleed" in lower:
        return (
            "If safe, apply pressure to active bleeding and avoid moving severe injuries. "
            "How many injured people are currently with you?"
        )
    if "fire" in lower or "smoke" in lower:
        return (
            "Move upwind and stay clear of enclosed smoke exposure. "
            "Are exits blocked or is anyone trapped inside?"
        )
    if "flood" in lower or "water" in lower:
        return (
            "Move to higher ground and avoid crossing moving water. "
            "What is current water depth near your location?"
        )
    return (
        "Stay in the safest reachable position and avoid isolated movement. "
        "Can you confirm injury count and immediate hazards around you?"
    )


def _reassurance_message(priority_score: int, summary: str) -> str:
    if priority_score >= 90:
        return (
            "Emergency signal received. Keep this app open and move to immediate safe cover if possible. "
            f"Situation: {summary}"
        )
    return (
        "Report received and under analysis. Stay alert and keep location services enabled. "
        f"Situation: {summary}"
    )


def _parse_datetime(value: Any) -> datetime:
    raw = str(value or "").strip().replace("Z", "+00:00")
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return datetime.utcnow()


def _generate_ai_chat_reply(
    incident: MobileIncident,
    history: List[Dict[str, str]],
    user_text: str,
) -> str:
    ai_reply = gemini_chat_followup_response(
        incident_summary=incident.description_summary or incident.incident_type or "Emergency report",
        recent_messages=history,
        latest_user_message=user_text,
    )
    return ai_reply or _fallback_follow_up_reply(user_text)


def _create_ticket_from_payload(
    db: Session,
    payload: Dict[str, Any],
    idempotency_key: str,
    client_ip: str,
) -> Dict[str, Any]:
    existing_record = db.query(TicketCreationRecord).filter(
        TicketCreationRecord.idempotency_key == idempotency_key
    ).first()
    if existing_record:
        return {
            "ticket_id": existing_record.ticket_id,
            "status": "duplicate",
            "idempotency_key": idempotency_key,
        }

    external_id = str(payload.get("external_id") or payload.get("incident_id") or "").strip()
    if not external_id:
        external_id = f"APP-{uuid.uuid4().hex[:10].upper()}"

    existing_sos = db.query(SOSRequest).filter(SOSRequest.external_id == external_id).first()
    if existing_sos:
        ticket_id = str(existing_sos.id)
    else:
        priority_score = int(payload.get("priority_score", 50) or 50)
        mapped_priority = max(1, min(5, int(round(priority_score / 20.0))))
        sos = SOSRequest(
            external_id=external_id,
            status="Pending",
            people=max(1, int(payload.get("people", 1) or 1)),
            longitude=float(payload.get("longitude", 0) or 0),
            latitude=float(payload.get("latitude", 0) or 0),
            text=str(payload.get("text") or payload.get("summary") or "Mobile incident"),
            place=str(payload.get("place") or "Unknown"),
            category=str(payload.get("incident_type") or payload.get("category_hint") or "General Emergency"),
            priority=mapped_priority,
            notes=(
                f"source=mobile_ticket_creation_endpoint; "
                f"idempotency_key={idempotency_key}; "
                f"client_ip={client_ip}; "
                f"fraud_risk={payload.get('fraud_risk_score', 0)}"
            ),
            timestamp=_parse_datetime(payload.get("timestamp")),
        )
        db.add(sos)
        db.commit()
        db.refresh(sos)
        ticket_id = str(sos.id)

    record = TicketCreationRecord(
        idempotency_key=idempotency_key,
        incident_id=str(payload.get("incident_id") or external_id),
        ticket_id=ticket_id,
        payload=json.dumps(payload),
        status="created",
    )
    db.add(record)
    db.commit()

    return {
        "ticket_id": ticket_id,
        "status": "created",
        "idempotency_key": idempotency_key,
    }


@router.post("/tickets")
async def create_mobile_ticket(
    request: Request,
    metadata: str = Form(...),
    images: List[UploadFile] = File(default=[]),
    videos: List[UploadFile] = File(default=[]),
    audio_file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    try:
        metadata_json = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid metadata JSON: {exc}") from exc

    idempotency_key = _extract_idempotency_key(metadata_json)
    existing = db.query(MobileIncident).filter(MobileIncident.idempotency_key == idempotency_key).first()
    if existing:
        return {
            "ticket_id": existing.dispatched_ticket_id or existing.external_id or existing.id,
            "incident_id": existing.external_id or existing.id,
            "chat_session_id": existing.chat_session_id,
            "status": existing.dispatch_status.lower(),
            "priority_score": existing.priority_score,
            "reassurance_message": _reassurance_message(
                priority_score=existing.priority_score or 0,
                summary=existing.description_summary or "Emergency report",
            ),
            "idempotent_replay": True,
        }

    incident_ref = str(
        metadata_json.get("ticket_id_client")
        or metadata_json.get("external_id")
        or f"INC-{uuid.uuid4().hex[:12].upper()}"
    )

    saved_images = [await _save_upload(incident_ref, "images", item) for item in images]
    saved_videos = [await _save_upload(incident_ref, "videos", item) for item in videos]
    saved_audio = [await _save_upload(incident_ref, "audio", audio_file)] if audio_file else []
    media_manifest = {
        "images": saved_images,
        "videos": saved_videos,
        "audio": saved_audio,
    }

    ai_bundle = build_ai_incident_bundle(
        db=db,
        metadata=metadata_json,
        media_manifest=media_manifest,
        client_ip=(request.client.host if request.client else ""),
    )

    endpoint = _resolve_dispatch_endpoint(request)
    incident = MobileIncident(
        external_id=ai_bundle["external_id"],
        idempotency_key=ai_bundle["idempotency_key"],
        chat_session_id=ai_bundle["chat_session_id"],
        ticket_type="SOS" if ai_bundle["is_sos"] else "Normal",
        detected_categories=json.dumps(ai_bundle["detected_categories"]),
        primary_category=ai_bundle["primary_category"],
        incident_type=ai_bundle["incident_type"],
        severity_score=ai_bundle["severity_score"],
        location_density_score=ai_bundle["location_density_score"],
        weather_confirmation_score=ai_bundle["weather_confirmation_score"],
        fraud_risk_score=ai_bundle["fraud_risk_score"],
        priority_score=ai_bundle["priority_score"],
        nearby_ticket_count=ai_bundle["nearby_ticket_count"],
        latitude=ai_bundle["latitude"],
        longitude=ai_bundle["longitude"],
        event_timestamp=ai_bundle["event_timestamp"],
        text=ai_bundle["text"],
        voice_transcript=ai_bundle["voice_transcript"],
        description_summary=ai_bundle["summary"],
        device_id_hash=ai_bundle["device_id_hash"],
        client_ip=(request.client.host if request.client else ""),
        media_manifest=ai_bundle["media_manifest_json"],
        normalized_payload=json.dumps(ai_bundle["normalized_payload"]),
        verification_payload=json.dumps(ai_bundle["verification_payload"]),
        dispatch_payload=json.dumps(ai_bundle["dispatch_payload"]),
        dispatch_endpoint=endpoint,
        dispatch_status="Pending",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    dispatch_result = dispatch_ticket_with_retry(
        db=db,
        incident=incident,
        payload=ai_bundle["dispatch_payload"],
        endpoint=endpoint,
    ) if not _is_internal_dispatch_endpoint(request, endpoint) else None

    if dispatch_result is None:
        local_result = _create_ticket_from_payload(
            db=db,
            payload=ai_bundle["dispatch_payload"],
            idempotency_key=incident.idempotency_key,
            client_ip=(request.client.host if request.client else ""),
        )
        incident.dispatch_status = "Dispatched"
        incident.dispatched_ticket_id = str(local_result.get("ticket_id") or incident.external_id)
        incident.dispatch_error = None
        db.commit()
        db.refresh(incident)

        attempt = MobileDispatchAttempt(
            incident_id=incident.id,
            attempt_no=1,
            success=True,
            http_status=200,
            latency_ms=0,
            response_body=json.dumps(local_result),
            error_message=None,
        )
        db.add(attempt)
        db.commit()

        dispatch_result = {
            "success": True,
            "status_code": 200,
            "ticket_id": incident.dispatched_ticket_id,
            "attempts": 1,
            "response": local_result,
        }

    reassurance_message = _reassurance_message(
        priority_score=ai_bundle["priority_score"],
        summary=ai_bundle["summary"],
    )
    IN_MEMORY_CHAT[incident.chat_session_id] = [
        {
            "role": "assistant",
            "text": reassurance_message,
            "timestamp": _now_iso(),
        }
    ]

    status = "received" if dispatch_result["success"] else "queued"
    return {
        "ticket_id": dispatch_result.get("ticket_id") or incident.external_id or incident.id,
        "incident_id": incident.external_id or incident.id,
        "chat_session_id": incident.chat_session_id,
        "status": status,
        "priority_score": ai_bundle["priority_score"],
        "priority_lane": ai_bundle["priority_lane"],
        "incident_type": ai_bundle["incident_type"],
        "detected_categories": ai_bundle["detected_categories"],
        "summary": ai_bundle["summary"],
        "verification": ai_bundle["verification_payload"],
        "dispatch": {
            "success": dispatch_result["success"],
            "attempts": dispatch_result["attempts"],
            "endpoint": endpoint,
            "status_code": dispatch_result.get("status_code"),
            "error": dispatch_result.get("error"),
        },
        "reassurance_message": reassurance_message,
    }


@router.post("/chat/{chat_session_id}/messages")
async def mobile_chat(
    chat_session_id: str,
    message: MobileChatMessage,
    db: Session = Depends(get_db),
):
    incident = db.query(MobileIncident).filter(MobileIncident.chat_session_id == chat_session_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Chat session not found")

    history = IN_MEMORY_CHAT.setdefault(chat_session_id, [])
    history.append(
        {
            "role": message.role,
            "text": message.text,
            "timestamp": message.timestamp or _now_iso(),
        }
    )

    reply_text = _generate_ai_chat_reply(incident=incident, history=history, user_text=message.text)
    history.append({"role": "assistant", "text": reply_text, "timestamp": _now_iso()})
    IN_MEMORY_CHAT[chat_session_id] = history[-24:]

    return {
        "reply_text": reply_text,
        "incident_id": incident.external_id or incident.id,
        "priority_score": incident.priority_score,
    }


@router.post("/ai/voice-agent")
async def mobile_ai_voice_agent(
    chat_session_id: str = Form(...),
    audio_file: Optional[UploadFile] = File(default=None),
    text_hint: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    incident = db.query(MobileIncident).filter(MobileIncident.chat_session_id == chat_session_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Chat session not found")

    history = IN_MEMORY_CHAT.setdefault(chat_session_id, [])
    transcript = str(text_hint or "").strip()
    audio_reference = None

    if audio_file:
        saved_audio = await _save_upload(
            incident_ref=incident.external_id or incident.id or chat_session_id,
            bucket="chat_audio",
            file=audio_file,
        )
        audio_reference = saved_audio.get("relative_path")
        ai_transcript = gemini_transcribe_audio(saved_audio["disk_path"], language_hint="en")
        if ai_transcript:
            transcript = ai_transcript.strip()

    if not transcript:
        transcript = "Need assistance. Voice input could not be transcribed."

    history.append({"role": "user", "text": transcript, "timestamp": _now_iso()})
    reply_text = _generate_ai_chat_reply(incident=incident, history=history, user_text=transcript)
    history.append({"role": "assistant", "text": reply_text, "timestamp": _now_iso()})
    IN_MEMORY_CHAT[chat_session_id] = history[-24:]

    return {
        "transcript": transcript,
        "reply_text": reply_text,
        "incident_id": incident.external_id or incident.id,
        "priority_score": incident.priority_score,
        "audio_reference": audio_reference,
    }


@router.post("/ticket-creation-endpoint")
async def ticket_creation_endpoint(
    payload: Dict[str, Any],
    request: Request,
    idempotency_key_header: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    idempotency_key = (
        str(payload.get("idempotency_key") or idempotency_key_header or "").strip()
        or f"idem-{uuid.uuid4().hex}"
    )
    return _create_ticket_from_payload(
        db=db,
        payload=payload,
        idempotency_key=idempotency_key,
        client_ip=(request.client.host if request.client else ""),
    )


@router.post("/dispatch/retry-pending")
async def retry_pending_dispatch(
    request: Request,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    items = (
        db.query(MobileIncident)
        .filter(MobileIncident.dispatch_status.in_(["Queued", "Failed", "Pending"]))
        .order_by(MobileIncident.priority_score.desc(), MobileIncident.created_at.asc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    endpoint = _resolve_dispatch_endpoint(request)

    processed = 0
    success = 0
    failed = 0
    for incident in items:
        payload_text = incident.dispatch_payload or "{}"
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {}
        target_endpoint = incident.dispatch_endpoint or endpoint
        if _is_internal_dispatch_endpoint(request, target_endpoint):
            local = _create_ticket_from_payload(
                db=db,
                payload=payload,
                idempotency_key=incident.idempotency_key,
                client_ip=(request.client.host if request.client else ""),
            )
            incident.dispatch_status = "Dispatched"
            incident.dispatched_ticket_id = str(local.get("ticket_id") or incident.external_id)
            incident.dispatch_error = None
            db.commit()

            attempt = MobileDispatchAttempt(
                incident_id=incident.id,
                attempt_no=1,
                success=True,
                http_status=200,
                latency_ms=0,
                response_body=json.dumps(local),
                error_message=None,
            )
            db.add(attempt)
            db.commit()
            result = {"success": True}
        else:
            result = dispatch_ticket_with_retry(
                db=db,
                incident=incident,
                payload=payload,
                endpoint=target_endpoint,
            )
        processed += 1
        if result.get("success"):
            success += 1
        else:
            failed += 1

    return {
        "processed": processed,
        "success": success,
        "failed": failed,
    }


@router.get("/incidents/{incident_id}")
async def get_mobile_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = (
        db.query(MobileIncident)
        .filter((MobileIncident.id == incident_id) | (MobileIncident.external_id == incident_id))
        .first()
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "incident_id": incident.external_id or incident.id,
        "dispatch_status": incident.dispatch_status,
        "ticket_id": incident.dispatched_ticket_id,
        "priority_score": incident.priority_score,
        "incident_type": incident.incident_type,
        "summary": incident.description_summary,
        "verification": json.loads(incident.verification_payload or "{}"),
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
    }
