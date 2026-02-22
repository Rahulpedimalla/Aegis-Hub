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


PEOPLE_SUFFIX_REGEX = re.compile(
    r"\b(\d{1,4})\s*(people|persons|person|members|adults|children|injured|victims|trapped|missing|affected|casualties)\b",
    re.IGNORECASE,
)
PEOPLE_PREFIX_REGEX = re.compile(
    r"\b(people|persons|person|members|adults|children|injured|victims|trapped|missing|affected|casualties)\s*[:=-]?\s*(\d{1,4})\b",
    re.IGNORECASE,
)
COORDINATE_NEARBY_REGEX = re.compile(r"-?\d{1,2}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}", re.IGNORECASE)

PEOPLE_CONTEXT_TERMS = {
    "people",
    "persons",
    "members",
    "adults",
    "children",
    "child",
    "injured",
    "victims",
    "trapped",
    "missing",
    "affected",
}

WORD_NUMBER_MAP = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
}

WORD_NUMBER_PATTERN = re.compile(
    r"\b(?:"
    r"zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundred|thousand|and"
    r")(?:[\s-]+(?:"
    r"zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundred|thousand|and"
    r"))*\b",
    re.IGNORECASE,
)


def _normalize(text: Optional[str]) -> str:
    return " ".join((text or "").strip().lower().split())


def _word_number_to_int(phrase: str) -> Optional[int]:
    tokens = [token for token in phrase.lower().replace("-", " ").split() if token and token != "and"]
    if not tokens:
        return None

    total = 0
    current = 0
    consumed_any = False
    for token in tokens:
        value = WORD_NUMBER_MAP.get(token)
        if value is None:
            return None
        consumed_any = True
        if value == 100:
            current = max(1, current) * 100
        elif value == 1000:
            current = max(1, current) * 1000
            total += current
            current = 0
        else:
            current += value

    if not consumed_any:
        return None
    return total + current


def _extract_word_number_candidates(text: str) -> List[int]:
    candidates: List[int] = []
    if not text:
        return candidates

    normalized = text.lower()
    for match in WORD_NUMBER_PATTERN.finditer(normalized):
        phrase = match.group(0)
        value = _word_number_to_int(phrase)
        if value is None or value <= 0 or value > 10000:
            continue

        left = max(0, match.start() - 32)
        right = min(len(normalized), match.end() + 32)
        context = normalized[left:right]
        if any(term in context for term in PEOPLE_CONTEXT_TERMS):
            candidates.append(value)

    return candidates


def extract_people_count(text: Optional[str], fallback: int = 1) -> int:
    if not text:
        return max(1, fallback)

    candidates = []
    normalized = text.lower()

    for match in PEOPLE_SUFFIX_REGEX.finditer(normalized):
        raw_number = match.group(1)
        start = match.start(1)
        end = match.end(1)
        # Skip decimal fragments (e.g., coordinates like 17.45672).
        prev_char = normalized[start - 1] if start > 0 else " "
        next_char = normalized[end] if end < len(normalized) else " "
        if prev_char == "." or next_char == ".":
            continue
        try:
            value = int(raw_number)
            if 0 < value <= 10000:
                candidates.append(value)
        except ValueError:
            continue

    for match in PEOPLE_PREFIX_REGEX.finditer(normalized):
        raw_number = match.group(2)
        start = match.start(2)
        end = match.end(2)
        prev_char = normalized[start - 1] if start > 0 else " "
        next_char = normalized[end] if end < len(normalized) else " "
        if prev_char == "." or next_char == ".":
            continue
        try:
            value = int(raw_number)
            if 0 < value <= 10000:
                candidates.append(value)
        except ValueError:
            continue

    candidates.extend(_extract_word_number_candidates(normalized))

    if COORDINATE_NEARBY_REGEX.search(normalized) and not candidates:
        return max(1, fallback)

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
    best_match_score = 0
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
