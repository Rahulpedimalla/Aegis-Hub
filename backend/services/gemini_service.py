import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
GEMINI_MODELS_API = "https://generativelanguage.googleapis.com/v1beta/models?key={key}"
DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-pro-latest"]
ALLOWED_DIVISIONS = {"Rescue", "Medical", "Logistics", "Communication"}
_MODEL_CACHE: Dict[str, List[str]] = {}


def _extract_json(raw_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None

    # Try direct parse first.
    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Fallback: pull first JSON object from text.
    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _clamp_priority(value: Any, fallback: int) -> int:
    try:
        priority = int(value)
        return max(1, min(5, priority))
    except Exception:
        return fallback


def _sanitize_division(value: Any, fallback: str) -> str:
    text = str(value or "").strip().title()
    if text in ALLOWED_DIVISIONS:
        return text
    return fallback


def _normalize_model_name(model_name: str) -> str:
    raw = (model_name or "").strip()
    if raw.startswith("models/"):
        return raw.split("/", 1)[1]
    return raw


def _fetch_models_supporting_generation(api_key: str, timeout_seconds: int = 5) -> List[str]:
    if api_key in _MODEL_CACHE:
        return _MODEL_CACHE[api_key]

    url = GEMINI_MODELS_API.format(key=api_key)
    req = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        _MODEL_CACHE[api_key] = []
        return []

    models = payload.get("models") or []
    candidates: List[str] = []
    for model in models:
        methods = model.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        name = _normalize_model_name(str(model.get("name", "")))
        if name:
            candidates.append(name)

    _MODEL_CACHE[api_key] = candidates
    return candidates


def _model_candidates(api_key: str, explicit_model: Optional[str]) -> List[str]:
    ordered: List[str] = []

    def add(candidate: Optional[str]) -> None:
        normalized = _normalize_model_name(candidate or "")
        if normalized and normalized not in ordered:
            ordered.append(normalized)

    add(explicit_model)
    for model in FALLBACK_MODELS:
        add(model)

    available = _fetch_models_supporting_generation(api_key)
    if not available:
        return ordered

    in_available = [m for m in ordered if m in available]
    remaining = [m for m in available if m not in in_available and ("gemini" in m or "gemma" in m)]
    # Keep list bounded to avoid long retry chains in hot paths.
    return (in_available + remaining)[:8]


def gemini_triage(
    text: str,
    people: int,
    category_hint: Optional[str] = None,
    place: Optional[str] = None,
    timeout_seconds: int = 8,
) -> Optional[Dict[str, Any]]:
    """
    Ask Gemini to classify SOS and suggest category/priority/division.
    Returns None on any error or when API key is unavailable.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    model_from_env = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    models_to_try = _model_candidates(api_key, model_from_env)
    if not models_to_try:
        models_to_try = [_normalize_model_name(model_from_env or DEFAULT_MODEL)]

    prompt = (
        "You are an emergency triage AI for Telangana disaster response.\n"
        "Classify incident and return STRICT JSON only with keys:\n"
        "category (string), priority (1-5 int), division_type (one of Rescue, Medical, Logistics, Communication),\n"
        "required_skills (array of short strings), urgency_level (Critical|High|Medium|Low), confidence (0-1 number).\n"
        "No markdown, no prose.\n\n"
        f"place={place or ''}\n"
        f"people={people}\n"
        f"category_hint={category_hint or ''}\n"
        f"text={text or ''}\n"
    )

    contents = [{"parts": [{"text": prompt}]}]
    generation_base = {
        "temperature": 0.1,
        "maxOutputTokens": 512,
    }
    body_variants = [
        {
            "contents": contents,
            "generationConfig": {
                **generation_base,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        },
        {
            "contents": contents,
            "generationConfig": generation_base,
        },
    ]

    for model in models_to_try:
        payload = None
        url = GEMINI_API_URL.format(model=model, key=api_key)
        for body in body_variants:
            req = urllib.request.Request(
                url=url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
                payload = None
                continue

        if not payload:
            continue

        candidates = payload.get("candidates") or []
        if not candidates:
            continue

        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        if not parts:
            continue

        raw_text = parts[0].get("text", "")
        parsed = _extract_json(raw_text)
        if not parsed:
            continue

        category = str(parsed.get("category") or "").strip() or "General Emergency"
        priority = _clamp_priority(parsed.get("priority"), fallback=3)
        division_type = _sanitize_division(parsed.get("division_type"), fallback="Rescue")
        required_skills = parsed.get("required_skills")
        if not isinstance(required_skills, list):
            required_skills = []
        required_skills = [str(s).strip().lower() for s in required_skills if str(s).strip()]
        urgency = str(parsed.get("urgency_level") or "").strip().title()
        if urgency not in {"Critical", "High", "Medium", "Low"}:
            urgency = "Medium"
        try:
            confidence = float(parsed.get("confidence", 0.7))
            confidence = max(0.0, min(1.0, confidence))
        except Exception:
            confidence = 0.7

        return {
            "category": category,
            "priority": priority,
            "division_type": division_type,
            "required_skills": required_skills,
            "urgency_level": urgency,
            "confidence": round(confidence, 2),
        }

    return None
