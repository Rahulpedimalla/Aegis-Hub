from typing import Dict, List, Optional

from services.geo_utils import haversine_km, infer_telangana_anchor


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def _category_match_score(category: str, target: str) -> float:
    c1 = (category or "").lower()
    c2 = (target or "").lower()
    if not c1 or not c2:
        return 0.3
    if c1 in c2 or c2 in c1:
        return 1.0
    token_overlap = len(set(c1.split()) & set(c2.split()))
    return 0.6 if token_overlap > 0 else 0.3


def _infer_division_type(category: str) -> str:
    c = (category or "").lower()
    if any(k in c for k in ["medical", "ambulance", "trauma", "hospital"]):
        return "Medical"
    if any(k in c for k in ["food", "shelter", "logistics", "supply"]):
        return "Logistics"
    if any(k in c for k in ["communication", "coordination", "network"]):
        return "Communication"
    return "Rescue"


def _org_anchor(org) -> tuple[float, float]:
    # Organization does not have explicit coordinates in the current schema.
    # Infer anchor coordinate from address/name for Telangana-aware distance.
    seed_text = f"{org.name or ''} {org.address or ''}"
    return infer_telangana_anchor(seed_text)


def _staff_anchor(staff) -> tuple[float, float]:
    seed_text = f"{staff.current_location or ''} {staff.name or ''}"
    return infer_telangana_anchor(seed_text)


def recommend_assignment(
    sos,
    organizations: List,
    staff_members: List,
    divisions: List,
    triage_context: Optional[Dict] = None,
) -> Dict:
    """
    Score and return the best organization, staff, and division for an SOS.
    """
    sos_lat = float(sos.latitude)
    sos_lon = float(sos.longitude)
    sos_category = sos.category or ""
    triage_context = triage_context or {}
    desired_division_type = triage_context.get("division_type") or _infer_division_type(sos_category)
    required_skills = [s.lower() for s in (triage_context.get("required_skills") or []) if s]
    assignment_basis = triage_context.get("source", "rules")

    ranked_orgs = []
    for org in organizations:
        if (org.status or "").lower() == "inactive":
            continue
        if org.capacity and org.current_load is not None and org.current_load >= org.capacity:
            continue

        lat, lon = _org_anchor(org)
        distance_km = haversine_km(sos_lat, sos_lon, lat, lon)
        distance_score = max(0.0, 1 - min(distance_km / 250.0, 1))
        capacity_score = _safe_ratio((org.capacity or 0) - (org.current_load or 0), (org.capacity or 1))
        category_score = _category_match_score(org.category, desired_division_type)
        total_score = (0.45 * distance_score) + (0.30 * capacity_score) + (0.25 * category_score)

        ranked_orgs.append({
            "id": str(org.id),
            "name": org.name,
            "type": org.type,
            "category": org.category,
            "contact_person": org.contact_person,
            "contact_phone": org.contact_phone,
            "distance_km": round(distance_km, 2),
            "estimated_response_time": round(max(5.0, distance_km * 2.5), 1),
            "score": round(total_score * 100, 1),
        })

    ranked_orgs.sort(key=lambda x: x["score"], reverse=True)

    ranked_staff = []
    for person in staff_members:
        if (person.status or "").lower() != "active":
            continue
        if (person.availability or "").lower() != "available":
            continue

        lat, lon = _staff_anchor(person)
        distance_km = haversine_km(sos_lat, sos_lon, lat, lon)
        distance_score = max(0.0, 1 - min(distance_km / 250.0, 1))
        skills = (person.skills or "").lower()
        if required_skills:
            matched = sum(1 for skill in required_skills if skill in skills)
            skill_score = max(0.3, min(1.0, matched / max(1, len(required_skills))))
        else:
            skill_score = _category_match_score(skills, desired_division_type)
        total_score = (0.55 * distance_score) + (0.45 * skill_score)

        ranked_staff.append({
            "id": str(person.id),
            "name": person.name,
            "role": person.role,
            "skills": person.skills,
            "distance_km": round(distance_km, 2),
            "score": round(total_score * 100, 1),
        })

    ranked_staff.sort(key=lambda x: x["score"], reverse=True)

    ranked_divisions = []
    for div in divisions:
        if (div.status or "").lower() == "inactive":
            continue
        if div.capacity and div.current_load is not None and div.current_load >= div.capacity:
            continue

        capacity_score = _safe_ratio((div.capacity or 0) - (div.current_load or 0), (div.capacity or 1))
        type_score = _category_match_score(div.type, desired_division_type)
        total_score = (0.65 * capacity_score) + (0.35 * type_score)

        ranked_divisions.append({
            "id": str(div.id),
            "name": div.name,
            "type": div.type,
            "score": round(total_score * 100, 1),
        })

    ranked_divisions.sort(key=lambda x: x["score"], reverse=True)

    best_org = ranked_orgs[0] if ranked_orgs else None
    best_staff = ranked_staff[0] if ranked_staff else None
    best_div = ranked_divisions[0] if ranked_divisions else None

    overall = 0.0
    parts = []
    for candidate in [best_org, best_staff, best_div]:
        if candidate:
            parts.append(candidate["score"])
    if parts:
        overall = round(sum(parts) / len(parts), 1)

    return {
        "recommended_assignment": {
            "organization": best_org,
            "staff": best_staff,
            "division": best_div,
            "alternatives": {
                "organizations": ranked_orgs[1:4],
                "staff": ranked_staff[1:4],
                "divisions": ranked_divisions[1:4],
            },
        },
        "assignment_score": overall,
        "assignment_context": {
            "desired_division_type": desired_division_type,
            "required_skills": required_skills,
            "basis": assignment_basis,
        },
    }
