from typing import Any, Dict, List, Optional, Sequence, Set

from services.geo_utils import haversine_km, infer_telangana_anchor


DISASTER_PROFILES = {
    "flood": {
        "keywords": ["flood", "water", "inundation", "submerged", "drown", "boat", "swift water", "rain"],
        "division_types": {"Rescue", "Logistics"},
    },
    "fire": {
        "keywords": ["fire", "smoke", "burn", "blaze", "explosion", "gas leak", "flame"],
        "division_types": {"Rescue", "Medical"},
    },
    "medical": {
        "keywords": ["medical", "injury", "injured", "bleeding", "trauma", "fracture", "ambulance"],
        "division_types": {"Medical"},
    },
    "relief": {
        "keywords": ["shelter", "food", "relief", "displaced", "homeless", "camp", "supplies"],
        "division_types": {"Logistics"},
    },
    "infrastructure": {
        "keywords": ["power", "electric", "road", "bridge", "network", "communication", "infrastructure"],
        "division_types": {"Communication", "Logistics"},
    },
}


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _category_match_score(category: str, target: str) -> float:
    c1 = _normalize_text(category)
    c2 = _normalize_text(target)
    if not c1 or not c2:
        return 0.3
    if c1 in c2 or c2 in c1:
        return 1.0
    token_overlap = len(set(c1.split()) & set(c2.split()))
    return 0.6 if token_overlap > 0 else 0.2


def _infer_division_type(category: str) -> str:
    c = _normalize_text(category)
    if any(k in c for k in ["medical", "ambulance", "trauma", "hospital"]):
        return "Medical"
    if any(k in c for k in ["food", "shelter", "logistics", "supply"]):
        return "Logistics"
    if any(k in c for k in ["communication", "coordination", "network"]):
        return "Communication"
    return "Rescue"


def _stringify_id(value) -> str:
    return str(value) if value is not None else ""


def _org_anchor(org) -> tuple[float, float]:
    # Organization does not have explicit coordinates in the current schema.
    # Infer anchor coordinate from address/name for Telangana-aware distance.
    seed_text = f"{org.name or ''} {org.address or ''}"
    return infer_telangana_anchor(seed_text)


def _staff_anchor(staff) -> tuple[float, float]:
    seed_text = f"{staff.current_location or ''} {staff.name or ''}"
    return infer_telangana_anchor(seed_text)


def _tag_overlap(text: str, tags: Sequence[str]) -> int:
    normalized = _normalize_text(text)
    if not normalized or not tags:
        return 0
    return sum(1 for tag in tags if tag in normalized)


def _detect_incident_domains(text: str) -> List[str]:
    normalized = _normalize_text(text)
    scored = []
    for domain, profile in DISASTER_PROFILES.items():
        hit_count = _tag_overlap(normalized, profile["keywords"])
        if hit_count > 0:
            scored.append((domain, hit_count))
    if not scored:
        return []
    scored.sort(key=lambda item: item[1], reverse=True)
    return [item[0] for item in scored[:2]]


def _candidate_tier(
    *,
    org_domain_match: bool,
    staff_domain_match: bool,
    required_skill_hits: int,
    is_available: bool,
) -> int:
    if org_domain_match and staff_domain_match and is_available:
        return 1
    if org_domain_match and staff_domain_match:
        return 2
    if org_domain_match and required_skill_hits > 0 and is_available:
        return 3
    if org_domain_match and required_skill_hits > 0:
        return 4
    if org_domain_match and is_available:
        return 5
    if is_available:
        return 6
    return 7


def _staff_payload(row: Dict) -> Dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "role": row["role"],
        "skills": row["skills"],
        "availability": row["availability"],
        "distance_km": row["distance_km"],
        "score": row["score"],
    }


def _division_payload(row: Optional[Dict]) -> Optional[Dict]:
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "score": row["score"],
    }


def _parse_constraints(assignment_constraints: Optional[Dict]) -> tuple[Set[str], Set[str], Optional[str]]:
    constraints = assignment_constraints or {}
    exclude_staff_ids = {
        str(item)
        for item in (constraints.get("exclude_staff_ids") or [])
        if str(item or "").strip()
    }
    exclude_org_ids = {
        str(item)
        for item in (constraints.get("exclude_org_ids") or [])
        if str(item or "").strip()
    }
    preferred_org_id = str(constraints.get("preferred_org_id") or "").strip() or None
    return exclude_staff_ids, exclude_org_ids, preferred_org_id


def recommend_assignment(
    sos,
    organizations: List,
    staff_members: List,
    divisions: List,
    triage_context: Optional[Dict] = None,
    assignment_constraints: Optional[Dict] = None,
) -> Dict:
    """
    Score and return the best organization, staff, and division for an SOS.
    Selection policy:
    1) Disaster-domain matching org + staff
    2) Required-skill fallback
    3) Always assign best available/busy active staff if needed
    """
    sos_lat = float(sos.latitude)
    sos_lon = float(sos.longitude)
    sos_category = sos.category or ""
    triage_context = triage_context or {}
    desired_division_type = triage_context.get("division_type") or _infer_division_type(sos_category)
    required_skills = [s.lower() for s in (triage_context.get("required_skills") or []) if s]
    assignment_basis = triage_context.get("source", "rules")
    exclude_staff_ids, exclude_org_ids, preferred_org_id = _parse_constraints(assignment_constraints)

    incident_text = " ".join(
        filter(
            None,
            [
                sos_category,
                triage_context.get("normalized_text"),
                " ".join(required_skills),
                desired_division_type,
            ],
        )
    )
    incident_domains = _detect_incident_domains(incident_text)
    incident_domain_tags: Set[str] = set()
    preferred_division_types: Set[str] = {desired_division_type}
    for domain in incident_domains:
        profile = DISASTER_PROFILES.get(domain) or {}
        incident_domain_tags.update(profile.get("keywords") or [])
        preferred_division_types.update(profile.get("division_types") or set())

    division_by_org: Dict[str, List] = {}
    division_by_id: Dict[str, Any] = {}
    for div in divisions:
        div_id = _stringify_id(div.id)
        division_by_id[div_id] = div
        division_by_org.setdefault(_stringify_id(div.organization_id), []).append(div)

    staff_by_org: Dict[str, List] = {}
    for person in staff_members:
        staff_by_org.setdefault(_stringify_id(person.organization_id), []).append(person)

    org_lookup: Dict[str, Any] = {_stringify_id(org.id): org for org in organizations}
    assignment_candidates: List[Dict] = []
    fallback_org_candidates: List[Dict] = []

    for org in organizations:
        org_id = _stringify_id(org.id)
        if org_id in exclude_org_ids:
            continue
        if (org.status or "").lower() == "inactive":
            continue
        if org.capacity and org.current_load is not None and org.current_load >= org.capacity:
            continue

        org_divisions = division_by_org.get(org_id, [])
        org_division_text = " ".join(
            f"{d.name or ''} {d.type or ''} {d.description or ''}" for d in org_divisions
        )
        org_profile = f"{org.name or ''} {org.type or ''} {org.category or ''} {org.address or ''} {org_division_text}"
        org_domain_hits = _tag_overlap(org_profile, tuple(incident_domain_tags))
        org_domain_match = (len(incident_domain_tags) == 0) or (org_domain_hits > 0)

        org_lat, org_lon = _org_anchor(org)
        org_distance_km = haversine_km(sos_lat, sos_lon, org_lat, org_lon)
        org_distance_score = max(0.0, 1 - min(org_distance_km / 250.0, 1))
        org_capacity_score = _safe_ratio((org.capacity or 0) - (org.current_load or 0), (org.capacity or 1))
        org_category_score = _category_match_score(
            org_profile,
            f"{' '.join(incident_domains)} {desired_division_type} {sos_category}",
        )
        domain_score = 1.0 if org_domain_match else 0.15
        org_score = (
            (0.35 * org_distance_score)
            + (0.25 * org_capacity_score)
            + (0.25 * org_category_score)
            + (0.15 * domain_score)
        )

        org_payload = {
            "id": org_id,
            "name": org.name,
            "type": org.type,
            "category": org.category,
            "contact_person": org.contact_person,
            "contact_phone": org.contact_phone,
            "distance_km": round(org_distance_km, 2),
            "estimated_response_time": round(max(5.0, org_distance_km * 2.5), 1),
            "score": round(org_score * 100, 1),
        }
        fallback_org_candidates.append(org_payload)

        candidate_div_rows = []
        for div in org_divisions:
            if (div.status or "").lower() == "inactive":
                continue
            if div.capacity and div.current_load is not None and div.current_load >= div.capacity:
                continue
            capacity_score = _safe_ratio((div.capacity or 0) - (div.current_load or 0), (div.capacity or 1))
            type_score = _category_match_score(div.type, f"{desired_division_type} {' '.join(incident_domains)}")
            preferred_type_boost = 0.2 if (div.type or "").strip() in preferred_division_types else 0.0
            division_score_raw = min(1.0, (0.55 * capacity_score) + (0.35 * type_score) + preferred_type_boost)
            candidate_div_rows.append(
                {
                    "id": _stringify_id(div.id),
                    "organization_id": org_id,
                    "name": div.name,
                    "type": div.type,
                    "score": round(division_score_raw * 100, 1),
                    "_score_raw": division_score_raw,
                }
            )

        candidate_div_rows.sort(key=lambda x: x["_score_raw"], reverse=True)
        best_div_any = candidate_div_rows[0] if candidate_div_rows else None

        org_staff = staff_by_org.get(org_id, [])
        available_staff_count = 0
        for person in org_staff:
            if (person.status or "").lower() != "active":
                continue
            person_id = _stringify_id(person.id)
            if person_id in exclude_staff_ids:
                continue

            is_available = (person.availability or "").lower() == "available"
            if is_available:
                available_staff_count += 1

            lat, lon = _staff_anchor(person)
            distance_km = haversine_km(sos_lat, sos_lon, lat, lon)
            distance_score = max(0.0, 1 - min(distance_km / 250.0, 1))
            staff_profile = _normalize_text(
                f"{person.name or ''} {person.role or ''} {person.skills or ''} {person.current_location or ''}"
            )
            staff_domain_hits = _tag_overlap(staff_profile, tuple(incident_domain_tags))
            required_skill_hits = sum(1 for skill in required_skills if skill in staff_profile)
            if required_skills:
                required_skill_score = max(0.1, min(1.0, required_skill_hits / len(required_skills)))
            else:
                required_skill_score = _category_match_score(staff_profile, f"{desired_division_type} {sos_category}")

            staff_domain_match = (len(incident_domain_tags) == 0) or (staff_domain_hits > 0)
            domain_staff_score = 1.0 if staff_domain_match else 0.15
            availability_score = 1.0 if is_available else 0.25
            staff_score_raw = (
                (0.30 * required_skill_score)
                + (0.30 * distance_score)
                + (0.25 * availability_score)
                + (0.15 * domain_staff_score)
            )

            person_division = division_by_id.get(_stringify_id(person.division_id))
            selected_div = None
            if person_division and (person_division.status or "").lower() != "inactive":
                selected_div = {
                    "id": _stringify_id(person_division.id),
                    "organization_id": org_id,
                    "name": person_division.name,
                    "type": person_division.type,
                    "score": round(
                        (
                            100
                            * (
                                0.65
                                * _safe_ratio(
                                    (person_division.capacity or 0) - (person_division.current_load or 0),
                                    (person_division.capacity or 1),
                                )
                                + 0.35 * _category_match_score(person_division.type, desired_division_type)
                            )
                        ),
                        1,
                    ),
                    "_score_raw": (
                        0.65
                        * _safe_ratio(
                            (person_division.capacity or 0) - (person_division.current_load or 0),
                            (person_division.capacity or 1),
                        )
                        + 0.35 * _category_match_score(person_division.type, desired_division_type)
                    ),
                }
            elif best_div_any:
                selected_div = best_div_any

            division_raw = selected_div["_score_raw"] if selected_div else 0.0
            tier = _candidate_tier(
                org_domain_match=org_domain_match,
                staff_domain_match=staff_domain_match,
                required_skill_hits=required_skill_hits,
                is_available=is_available,
            )
            preference_boost = 0.08 if preferred_org_id and org_id == preferred_org_id else 0.0
            overall_raw = (0.40 * org_score) + (0.40 * staff_score_raw) + (0.20 * division_raw) + preference_boost

            assignment_candidates.append(
                {
                    "organization": org_payload,
                    "staff": {
                        "id": person_id,
                        "organization_id": org_id,
                        "name": person.name,
                        "role": person.role,
                        "skills": person.skills,
                        "availability": person.availability,
                        "distance_km": round(distance_km, 2),
                        "score": round(staff_score_raw * 100, 1),
                    },
                    "division": _division_payload(selected_div),
                    "available_staff_count": available_staff_count,
                    "score": round(overall_raw * 100, 1),
                    "_score_raw": overall_raw,
                    "_tier": tier,
                }
            )

    assignment_candidates.sort(key=lambda row: (row["_tier"], -row["_score_raw"]))

    if assignment_candidates:
        best = assignment_candidates[0]
        alt_orgs = [item["organization"] for item in assignment_candidates[1:4]]
        alt_staff = [_staff_payload(item["staff"]) for item in assignment_candidates[1:4]]
        alt_divs = [item["division"] for item in assignment_candidates[1:4] if item["division"]]

        return {
            "recommended_assignment": {
                "organization": best["organization"],
                "staff": _staff_payload(best["staff"]),
                "division": best["division"],
                "alternatives": {
                    "organizations": alt_orgs,
                    "staff": alt_staff,
                    "divisions": alt_divs,
                },
            },
            "candidate_assignments": [
                {
                    "organization": item["organization"],
                    "staff": _staff_payload(item["staff"]),
                    "division": item["division"],
                    "score": item["score"],
                    "available_staff_count": item["available_staff_count"],
                    "tier": item["_tier"],
                }
                for item in assignment_candidates[:10]
            ],
            "assignment_score": best["score"],
            "assignment_context": {
                "desired_division_type": desired_division_type,
                "required_skills": required_skills,
                "detected_domains": incident_domains,
                "basis": assignment_basis,
                "selection_policy": "domain_first_then_skill_then_availability_with_guaranteed_staff_fallback",
                "constraints": {
                    "excluded_staff": sorted(exclude_staff_ids),
                    "excluded_orgs": sorted(exclude_org_ids),
                    "preferred_org_id": preferred_org_id,
                },
            },
        }

    fallback_org_candidates.sort(key=lambda x: x["score"], reverse=True)
    fallback_org = fallback_org_candidates[0] if fallback_org_candidates else None

    # Hard fallback to avoid idle/unassigned tickets: pick best active responder even if busy.
    fallback_staff = None
    for person in sorted(
        [s for s in staff_members if (s.status or "").lower() == "active"],
        key=lambda p: ((p.availability or "").lower() != "available", p.name or ""),
    ):
        person_id = _stringify_id(person.id)
        if person_id in exclude_staff_ids:
            continue
        fallback_staff = person
        break

    if fallback_staff:
        fallback_org_model = org_lookup.get(_stringify_id(fallback_staff.organization_id))
        if fallback_org_model:
            fallback_org_payload = {
                "id": _stringify_id(fallback_org_model.id),
                "name": fallback_org_model.name,
                "type": fallback_org_model.type,
                "category": fallback_org_model.category,
                "contact_person": fallback_org_model.contact_person,
                "contact_phone": fallback_org_model.contact_phone,
                "distance_km": None,
                "estimated_response_time": None,
                "score": 50.0,
            }
        else:
            fallback_org_payload = fallback_org or {
                "id": _stringify_id(fallback_staff.organization_id),
                "name": "Fallback Organization",
                "type": None,
                "category": None,
                "contact_person": None,
                "contact_phone": None,
                "distance_km": None,
                "estimated_response_time": None,
                "score": 50.0,
            }

        fallback_division = division_by_id.get(_stringify_id(fallback_staff.division_id))
        return {
            "recommended_assignment": {
                "organization": fallback_org_payload,
                "staff": {
                    "id": _stringify_id(fallback_staff.id),
                    "name": fallback_staff.name,
                    "role": fallback_staff.role,
                    "skills": fallback_staff.skills,
                    "availability": fallback_staff.availability,
                    "distance_km": None,
                    "score": 50.0,
                },
                "division": (
                    {
                        "id": _stringify_id(fallback_division.id),
                        "name": fallback_division.name,
                        "type": fallback_division.type,
                        "score": 50.0,
                    }
                    if fallback_division
                    else None
                ),
                "alternatives": {
                    "organizations": fallback_org_candidates[1:4],
                    "staff": [],
                    "divisions": [],
                },
            },
            "candidate_assignments": [],
            "assignment_score": 50.0,
            "assignment_context": {
                "desired_division_type": desired_division_type,
                "required_skills": required_skills,
                "detected_domains": incident_domains,
                "basis": assignment_basis,
                "selection_policy": "hard_fallback_active_staff_even_when_busy",
            },
        }

    return {
        "recommended_assignment": {
            "organization": fallback_org,
            "staff": None,
            "division": None,
            "alternatives": {
                "organizations": fallback_org_candidates[1:4],
                "staff": [],
                "divisions": [],
            },
        },
        "candidate_assignments": [],
        "assignment_score": fallback_org["score"] if fallback_org else 0.0,
        "assignment_context": {
            "desired_division_type": desired_division_type,
            "required_skills": required_skills,
            "detected_domains": incident_domains,
            "basis": assignment_basis,
            "selection_policy": "no_staff_available_org_only",
        },
    }
