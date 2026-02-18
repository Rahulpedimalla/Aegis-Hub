import re
from typing import Dict, List, Optional

from services.gemini_service import gemini_triage

CATEGORY_RULES = {
    "Flood Rescue": {
        "keywords": ["flood", "water", "inundation", "submerged", "boat", "drowning"],
        "base_priority": 4,
        "required_skills": ["rescue", "boat", "swimming", "evacuation"],
    },
    "Medical Emergency": {
        "keywords": ["injury", "injured", "bleeding", "fracture", "pregnant", "medical", "ambulance", "heart"],
        "base_priority": 4,
        "required_skills": ["medical", "first aid", "trauma", "paramedic"],
    },
    "Fire Emergency": {
        "keywords": ["fire", "smoke", "burning", "explosion", "gas leak"],
        "base_priority": 5,
        "required_skills": ["fire", "rescue", "evacuation"],
    },
    "Food and Shelter": {
        "keywords": ["hungry", "food", "shelter", "homeless", "displaced", "relief camp"],
        "base_priority": 3,
        "required_skills": ["relief", "logistics", "shelter"],
    },
    "Power and Infrastructure": {
        "keywords": ["power", "electric", "road blocked", "bridge", "infrastructure", "communication down"],
        "base_priority": 2,
        "required_skills": ["logistics", "engineering", "coordination"],
    },
}


HIGH_RISK_TERMS = {
    "life threatening": 2,
    "critical": 2,
    "urgent": 1,
    "trapped": 1,
    "children": 1,
    "elderly": 1,
    "disabled": 1,
    "pregnant": 1,
}


PEOPLE_REGEX = re.compile(r"\b(\d{1,4})\s*(people|persons|members|adults|children)?\b", re.IGNORECASE)


def _normalize(text: Optional[str]) -> str:
    return " ".join((text or "").strip().lower().split())


def extract_people_count(text: Optional[str], fallback: int = 1) -> int:
    if not text:
        return max(1, fallback)

    candidates = []
    for match in PEOPLE_REGEX.findall(text):
        try:
            value = int(match[0])
            if 0 < value <= 10000:
                candidates.append(value)
        except ValueError:
            continue

    if candidates:
        return max(1, max(candidates))
    return max(1, fallback)


def _keyword_overlap_score(text: str, keywords: List[str]) -> int:
    score = 0
    for key in keywords:
        if key in text:
            score += 1
    return score


def _infer_division_type(category: str, required_skills: List[str], text: str) -> str:
    merged = f"{category} {' '.join(required_skills)} {text}".lower()
    if any(k in merged for k in ["medical", "ambulance", "injury", "trauma", "hospital"]):
        return "Medical"
    if any(k in merged for k in ["logistics", "food", "shelter", "transport", "supplies"]):
        return "Logistics"
    if any(k in merged for k in ["communication", "network", "control room", "coordination", "public alert"]):
        return "Communication"
    return "Rescue"


def triage_sos(
    text: Optional[str],
    voice_transcript: Optional[str],
    people: Optional[int],
    category_hint: Optional[str] = None,
    environmental_risk: int = 0,
    place: Optional[str] = None,
) -> Dict:
    """
    Lightweight AI triage for incoming SOS.
    Uses keyword matching + risk factors to estimate category and priority.
    """
    merged = _normalize(" ".join(filter(None, [text, voice_transcript, category_hint, place])))
    extracted_people = extract_people_count(merged, people or 1)

    best_category = "General Emergency"
    best_match_score = -1
    best_rule = None

    for category, rule in CATEGORY_RULES.items():
        score = _keyword_overlap_score(merged, rule["keywords"])
        if score > best_match_score:
            best_match_score = score
            best_category = category
            best_rule = rule

    if best_rule is None:
        best_rule = {
            "base_priority": 2,
            "required_skills": ["coordination"],
        }

    priority = best_rule["base_priority"]

    # Scale with number of affected people.
    if extracted_people >= 50:
        priority += 2
    elif extracted_people >= 15:
        priority += 1

    # Add text-based urgency terms.
    urgency_boost = sum(weight for term, weight in HIGH_RISK_TERMS.items() if term in merged)
    priority += urgency_boost

    # External risk from geospatial analysis.
    priority += environmental_risk
    priority = max(1, min(priority, 5))

    if priority >= 5:
        urgency_level = "Critical"
    elif priority == 4:
        urgency_level = "High"
    elif priority == 3:
        urgency_level = "Medium"
    else:
        urgency_level = "Low"

    confidence = 0.55 + min(0.4, best_match_score * 0.08)
    confidence = round(min(0.95, confidence), 2)

    default_result = {
        "normalized_text": merged,
        "category": best_category,
        "priority": priority,
        "urgency_level": urgency_level,
        "people": extracted_people,
        "required_skills": best_rule["required_skills"],
        "division_type": _infer_division_type(best_category, best_rule["required_skills"], merged),
        "confidence": confidence,
        "tags": [k for k in HIGH_RISK_TERMS if k in merged][:8],
        "source": "rules",
    }

    ai_result = gemini_triage(
        text=(text or voice_transcript or category_hint or ""),
        people=extracted_people,
        category_hint=category_hint,
        place=place,
    )
    if not ai_result:
        return default_result

    return {
        "normalized_text": merged,
        "category": ai_result["category"] or default_result["category"],
        "priority": max(default_result["priority"], ai_result["priority"]),
        "urgency_level": ai_result["urgency_level"] or default_result["urgency_level"],
        "people": extracted_people,
        "required_skills": ai_result["required_skills"] or default_result["required_skills"],
        "division_type": ai_result["division_type"] or default_result["division_type"],
        "confidence": max(default_result["confidence"], ai_result["confidence"]),
        "tags": default_result["tags"],
        "source": "gemini",
    }
