import json
import math
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import MobileIncident, SOSRequest
from services.gemini_service import (
    gemini_multimodal_media_insight,
    gemini_structured_incident_analysis,
    gemini_summarize_incident,
    gemini_transcribe_audio,
)
from services.triage_service import triage_sos
from services.weather_verification_service import verify_weather


REQUIRED_CATEGORIES_ORDER = ["Voice", "Image", "Video", "Text", "Emergency SOS"]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _parse_event_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.utcnow()
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except Exception:
        return datetime.utcnow()


def _extract_voice_transcript(metadata: Dict[str, Any]) -> str:
    raw = metadata.get("voice_transcript")
    if isinstance(raw, dict):
        return str(raw.get("raw_text") or "").strip()
    return str(raw or "").strip()


def _detect_categories(
    ticket_type: str,
    text: str,
    voice_text: str,
    media_manifest: Dict[str, Any],
) -> List[str]:
    images = media_manifest.get("images") or []
    videos = media_manifest.get("videos") or []
    audio = media_manifest.get("audio") or []

    detected = set()
    if voice_text or audio:
        detected.add("Voice")
    if images:
        detected.add("Image")
    if videos:
        detected.add("Video")
    if text:
        detected.add("Text")
    if ticket_type.upper() == "SOS":
        detected.add("Emergency SOS")

    return [category for category in REQUIRED_CATEGORIES_ORDER if category in detected]


def _primary_category(detected_categories: List[str]) -> str:
    if "Emergency SOS" in detected_categories:
        return "Emergency SOS"
    if "Voice" in detected_categories:
        return "Voice"
    if "Video" in detected_categories:
        return "Video"
    if "Image" in detected_categories:
        return "Image"
    return "Text"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return radius_km * 2 * math.asin(math.sqrt(a))


def _similar_incident(incident_type: str, candidate_type: str) -> bool:
    lhs = incident_type.lower().strip()
    rhs = (candidate_type or "").lower().strip()
    if not lhs or not rhs:
        return False
    return lhs in rhs or rhs in lhs


def _nearby_ticket_metrics(
    db: Session,
    latitude: float,
    longitude: float,
    incident_type: str,
    now_utc: datetime,
) -> Dict[str, int]:
    time_window_start = now_utc - timedelta(minutes=60)
    radius_km = 3.0

    nearby_total = 0
    nearby_similar = 0

    recent_sos = db.query(SOSRequest).filter(SOSRequest.created_at >= time_window_start).all()
    for row in recent_sos:
        if _haversine_km(latitude, longitude, row.latitude, row.longitude) <= radius_km:
            nearby_total += 1
            if _similar_incident(incident_type, row.category or ""):
                nearby_similar += 1

    recent_mobile = db.query(MobileIncident).filter(MobileIncident.created_at >= time_window_start).all()
    for row in recent_mobile:
        if _haversine_km(latitude, longitude, row.latitude, row.longitude) <= radius_km:
            nearby_total += 1
            if _similar_incident(incident_type, row.incident_type):
                nearby_similar += 1

    return {
        "nearby_total_count": nearby_total,
        "nearby_similar_count": nearby_similar,
    }


def _compute_fraud_risk(
    db: Session,
    device_id_hash: str,
    client_ip: str,
    text: str,
    voice_text: str,
    media_manifest: Dict[str, Any],
    now_utc: datetime,
    ai_credibility_risk: float,
) -> Dict[str, Any]:
    burst_window = now_utc - timedelta(minutes=10)
    long_window = now_utc - timedelta(hours=24)
    normalized_text = " ".join(f"{text} {voice_text}".lower().split())

    same_device_recent = 0
    same_ip_recent = 0
    exact_text_matches = 0

    recent = db.query(MobileIncident).filter(MobileIncident.created_at >= long_window).all()
    for row in recent:
        if row.created_at >= burst_window and device_id_hash and row.device_id_hash == device_id_hash:
            same_device_recent += 1
        if row.created_at >= burst_window and client_ip and row.client_ip == client_ip:
            same_ip_recent += 1
        previous_text = " ".join(f"{row.text or ''} {row.voice_transcript or ''}".lower().split())
        if normalized_text and previous_text == normalized_text:
            exact_text_matches += 1

    low_information = int((not normalized_text or len(normalized_text) < 12) and not any(media_manifest.values()))

    heuristic_score = 0.0
    if same_device_recent >= 3:
        heuristic_score += 0.35
    if same_ip_recent >= 5:
        heuristic_score += 0.25
    if exact_text_matches >= 2:
        heuristic_score += 0.25
    if low_information:
        heuristic_score += 0.15
    heuristic_score = max(0.0, min(1.0, heuristic_score))

    ai_score = max(0.0, min(1.0, ai_credibility_risk))
    fraud_score = round((0.65 * heuristic_score) + (0.35 * ai_score), 3)
    return {
        "fraud_risk_score": fraud_score,
        "heuristic_risk_score": round(heuristic_score, 3),
        "ai_credibility_risk": round(ai_score, 3),
        "same_device_recent_10m": same_device_recent,
        "same_ip_recent_10m": same_ip_recent,
        "exact_text_matches_24h": exact_text_matches,
        "low_information_signal": bool(low_information),
    }


def _priority_score(
    severity_score: float,
    location_density_score: float,
    weather_confirmation_score: float,
    is_sos: bool,
    fraud_risk_score: float,
) -> int:
    if is_sos:
        return 100
    raw = 100.0 * (
        (0.50 * severity_score)
        + (0.30 * location_density_score)
        + (0.20 * weather_confirmation_score)
    )
    adjusted = raw * (1 - (0.40 * fraud_risk_score))
    return int(max(1, min(99, round(adjusted))))


def _priority_lane(priority_score: int, is_sos: bool) -> str:
    if is_sos or priority_score >= 90:
        return "p0"
    if priority_score >= 70:
        return "p1"
    if priority_score >= 40:
        return "p2"
    return "p3"


def _media_paths(manifest: Dict[str, Any], bucket: str) -> List[str]:
    refs = manifest.get(bucket) or []
    results = []
    for ref in refs:
        path = str(ref.get("disk_path") or "").strip()
        if path:
            results.append(path)
    return results


def build_ai_incident_bundle(
    db: Session,
    metadata: Dict[str, Any],
    media_manifest: Dict[str, Any],
    client_ip: str,
) -> Dict[str, Any]:
    ticket_type = str(metadata.get("ticket_type") or "Normal")
    text = str(metadata.get("text") or "").strip()
    voice_text = _extract_voice_transcript(metadata)

    latitude = _to_float(metadata.get("latitude"), 0.0)
    longitude = _to_float(metadata.get("longitude"), 0.0)
    location_accuracy = _to_float(metadata.get("location_accuracy_m"), 0.0)
    event_timestamp = _parse_event_timestamp(metadata.get("timestamp"))

    nested_metadata = metadata.get("metadata") or {}
    if not isinstance(nested_metadata, dict):
        nested_metadata = {}
    device_info = metadata.get("device_info") or {}
    if not isinstance(device_info, dict):
        device_info = {}
    device_id_hash = str(device_info.get("device_id_hash") or "").strip()

    image_paths = _media_paths(media_manifest, "images")
    video_paths = _media_paths(media_manifest, "videos")
    audio_paths = _media_paths(media_manifest, "audio")

    # AI STT fallback when raw transcript is not available from client.
    if not voice_text and audio_paths:
        transcribed = gemini_transcribe_audio(audio_paths[0], language_hint="en")
        if transcribed:
            voice_text = transcribed

    detected_categories = _detect_categories(
        ticket_type=ticket_type,
        text=text,
        voice_text=voice_text,
        media_manifest=media_manifest,
    )
    primary_category = _primary_category(detected_categories)

    image_insight = gemini_multimodal_media_insight(image_paths, context_hint="image evidence") if image_paths else None
    video_insight = gemini_multimodal_media_insight(video_paths, context_hint="video evidence") if video_paths else None

    combined_context = " ".join(
        item
        for item in [text, voice_text, image_insight or "", video_insight or ""]
        if str(item).strip()
    ).strip()

    ai_structured = gemini_structured_incident_analysis(
        context_text=combined_context or "No context provided",
        detected_categories=detected_categories,
    ) or {}

    people_hint = _to_int(metadata.get("people"), 1)
    if ai_structured.get("people_estimate"):
        people_hint = max(people_hint, _to_int(ai_structured.get("people_estimate"), people_hint))

    triage = triage_sos(
        text=text or combined_context,
        voice_transcript=voice_text,
        people=people_hint,
        category_hint=str(ai_structured.get("incident_type") or "").strip() or None,
        place=str(metadata.get("place") or "").strip() or None,
    )

    incident_type = (
        str(ai_structured.get("incident_type") or "").strip()
        or str(triage.get("category") or "General Emergency")
    )
    severity_score = max(
        float(ai_structured.get("severity_score") or 0.0),
        max(0.0, min(1.0, float(triage.get("priority", 1)) / 5.0)),
    )

    summary = str(ai_structured.get("concise_summary") or "").strip()
    if not summary:
        summary = gemini_summarize_incident(combined_context or text or voice_text or incident_type) or ""
    if not summary:
        summary = (combined_context or text or voice_text or "Emergency incident reported")[:180]
    if len(summary) > 180:
        summary = summary[:177] + "..."

    nearby_metrics = _nearby_ticket_metrics(
        db=db,
        latitude=latitude,
        longitude=longitude,
        incident_type=incident_type,
        now_utc=datetime.utcnow(),
    )
    nearby_ticket_count = nearby_metrics["nearby_total_count"]
    nearby_similar_count = nearby_metrics["nearby_similar_count"]
    location_density_score = max(0.0, min(1.0, nearby_similar_count / 12.0))

    weather = verify_weather(
        latitude=latitude,
        longitude=longitude,
        incident_type=incident_type,
        text=combined_context or summary,
    )
    weather_confirmation_score = float(weather.get("confirmation_score", 0.5))

    fraud = _compute_fraud_risk(
        db=db,
        device_id_hash=device_id_hash,
        client_ip=client_ip,
        text=text,
        voice_text=voice_text,
        media_manifest=media_manifest,
        now_utc=datetime.utcnow(),
        ai_credibility_risk=float(ai_structured.get("credibility_risk", 0.3) or 0.3),
    )
    fraud_risk_score = float(fraud.get("fraud_risk_score", 0.0))

    is_sos = ticket_type.upper() == "SOS" or primary_category == "Emergency SOS"
    priority_score = _priority_score(
        severity_score=severity_score,
        location_density_score=location_density_score,
        weather_confirmation_score=weather_confirmation_score,
        is_sos=is_sos,
        fraud_risk_score=fraud_risk_score,
    )
    priority_lane = _priority_lane(priority_score=priority_score, is_sos=is_sos)

    external_id = str(metadata.get("external_id") or metadata.get("ticket_id_client") or "").strip()
    idempotency_key = (
        str(nested_metadata.get("idempotency_key") or metadata.get("idempotency_key") or external_id).strip()
        or f"idem-{datetime.utcnow().timestamp()}"
    )
    chat_session_id = f"CHAT-{uuid.uuid5(uuid.NAMESPACE_DNS, idempotency_key).hex[:12]}"

    normalized_payload = {
        "idempotency_key": idempotency_key,
        "external_id": external_id,
        "ticket_type": "SOS" if is_sos else "Normal",
        "detected_categories": detected_categories,
        "primary_category": primary_category,
        "incident_type": incident_type,
        "summary": summary,
        "severity_score": round(severity_score, 3),
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "accuracy_m": location_accuracy,
            "source": "gps_or_client_metadata",
        },
        "event_timestamp": event_timestamp.isoformat(),
        "description": {
            "text": text,
            "voice_transcript": voice_text,
            "image_insight": image_insight or "",
            "video_insight": video_insight or "",
        },
        "device_info": device_info,
        "metadata": nested_metadata,
    }

    verification_payload = {
        "weather": weather,
        "nearby_metrics": nearby_metrics,
        "fraud": fraud,
        "location_density_score": round(location_density_score, 3),
        "weather_confirmation_score": round(weather_confirmation_score, 3),
    }

    dispatch_payload = {
        "incident_id": external_id or idempotency_key,
        "external_id": external_id or idempotency_key,
        "idempotency_key": idempotency_key,
        "ticket_type": "Emergency SOS" if is_sos else "Normal",
        "incident_type": incident_type,
        "timestamp": event_timestamp.isoformat(),
        "summary": summary,
        "text": text or summary,
        "voice_transcript": voice_text,
        "people": max(1, _to_int(triage.get("people"), people_hint)),
        "place": str(metadata.get("place") or "").strip() or f"{latitude:.5f},{longitude:.5f}",
        "category_hint": incident_type,
        "latitude": latitude,
        "longitude": longitude,
        "priority_score": priority_score,
        "priority_lane": priority_lane,
        "severity_score": round(severity_score, 3),
        "location_density_score": round(location_density_score, 3),
        "weather_confirmation_score": round(weather_confirmation_score, 3),
        "fraud_risk_score": round(fraud_risk_score, 3),
        "nearby_ticket_count": nearby_ticket_count,
        "device_info": device_info,
        "media_manifest": media_manifest,
        "source": "mobile_app_ai_pipeline",
        "analysis": {
            "triage": triage,
            "ai_structured": ai_structured,
            "verification": verification_payload,
        },
    }

    return {
        "idempotency_key": idempotency_key,
        "chat_session_id": chat_session_id,
        "external_id": external_id or idempotency_key,
        "event_timestamp": event_timestamp,
        "incident_type": incident_type,
        "summary": summary,
        "priority_score": priority_score,
        "priority_lane": priority_lane,
        "severity_score": round(severity_score, 3),
        "location_density_score": round(location_density_score, 3),
        "weather_confirmation_score": round(weather_confirmation_score, 3),
        "fraud_risk_score": round(fraud_risk_score, 3),
        "nearby_ticket_count": nearby_ticket_count,
        "detected_categories": detected_categories,
        "primary_category": primary_category,
        "text": text,
        "voice_transcript": voice_text,
        "latitude": latitude,
        "longitude": longitude,
        "device_id_hash": device_id_hash,
        "normalized_payload": normalized_payload,
        "verification_payload": verification_payload,
        "dispatch_payload": dispatch_payload,
        "media_manifest_json": json.dumps(media_manifest),
        "is_sos": is_sos,
    }
