from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import math
from datetime import datetime, timedelta
import asyncio
import uuid

from database import (
    get_db,
    SessionLocal,
    SOSRequest,
    Organization,
    Staff,
    Division,
    Shelter,
    Hospital,
    ResourceCenter,
    TicketUpdate,
)
from models import SOSRequestResponse
from routes.auth_routes import get_current_user, require_roles
from services.assignment_service import recommend_assignment
from services.geo_utils import infer_telangana_anchor
from services.triage_service import triage_sos
from services.workload_service import release_assignment_workload, transfer_assignment_workload
from services.staff_resolution_service import resolve_responder_staff

router = APIRouter()
ASSIGNMENT_RESPONSE_WINDOW_SECONDS = 60

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def _can_responder_act_on_sos(current_user, sos: SOSRequest, db: Session) -> tuple[bool, Optional[Staff]]:
    if (current_user.role or "").lower() != "responder":
        return False, None

    staff = resolve_responder_staff(current_user, db)
    if not staff:
        return False, None

    if not sos.assigned_to:
        return False, staff

    return str(sos.assigned_to) == str(staff.id), staff


def _historical_rejected_staff_ids(db: Session, sos_id: str) -> set[str]:
    rows = (
        db.query(TicketUpdate)
        .filter(
            TicketUpdate.ticket_id == str(sos_id),
            TicketUpdate.field_name == "assignment_rejection",
        )
        .all()
    )
    rejected: set[str] = set()
    for row in rows:
        rejected_id = str(row.old_value or "").strip()
        if rejected_id and rejected_id != "None":
            rejected.add(rejected_id)
    return rejected

async def auto_reassign_emergency(sos_id: str):
    """Automatically reassign emergency after response window if not accepted."""
    await asyncio.sleep(ASSIGNMENT_RESPONSE_WINDOW_SECONDS)

    db = SessionLocal()
    try:
        # Check if the emergency is still pending assignment
        sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
        if (
            sos
            and sos.status == "Pending Assignment"
            and sos.assignment_time
            and (datetime.utcnow() - sos.assignment_time).total_seconds() >= ASSIGNMENT_RESPONSE_WINDOW_SECONDS
        ):
            # Auto-reassign to next best team
            await reassign_to_next_best_team(
                sos_id,
                db,
                exclude_staff_ids=[str(sos.assigned_to)] if sos.assigned_to else [],
                preferred_org_id=str(sos.assigned_organization) if sos.assigned_organization else None,
            )
    finally:
        db.close()

async def reassign_to_next_best_team(
    sos_id: str,
    db: Session,
    exclude_staff_ids: Optional[List[str]] = None,
    exclude_org_ids: Optional[List[str]] = None,
    preferred_org_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Reassign emergency to next best team; prefers same org with a different responder first."""
    sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
    if not sos:
        return None

    old_org = sos.assigned_organization
    old_staff = sos.assigned_to
    old_division = sos.assigned_division

    triage = triage_sos(
        text=sos.text,
        voice_transcript=None,
        people=sos.people,
        category_hint=sos.category,
        place=sos.place,
    )
    resolved_preferred_org = preferred_org_id or (str(old_org) if old_org else None)
    resolved_exclude_staff = set(str(item) for item in (exclude_staff_ids or []) if str(item or "").strip())
    resolved_exclude_staff.update(_historical_rejected_staff_ids(db, sos_id))
    if old_staff:
        resolved_exclude_staff.add(str(old_staff))
    resolved_exclude_orgs = [str(item) for item in (exclude_org_ids or []) if str(item or "").strip()]

    def _scored_candidates(preferred_org: Optional[str]) -> List[Dict[str, Any]]:
        scored_payload = recommend_assignment(
            sos,
            db.query(Organization).all(),
            db.query(Staff).all(),
            db.query(Division).all(),
            triage_context=triage,
            assignment_constraints={
                "exclude_staff_ids": sorted(resolved_exclude_staff),
                "exclude_org_ids": resolved_exclude_orgs,
                "preferred_org_id": preferred_org,
            },
        )
        recommended_assignment = scored_payload.get("recommended_assignment", {})
        ranked = scored_payload.get("candidate_assignments", []) or []
        if not ranked and recommended_assignment.get("organization") and recommended_assignment.get("staff"):
            ranked = [
                {
                    "organization": recommended_assignment.get("organization"),
                    "staff": recommended_assignment.get("staff"),
                    "division": recommended_assignment.get("division"),
                    "score": scored_payload.get("assignment_score", 0),
                }
            ]
        return ranked

    candidates = _scored_candidates(resolved_preferred_org)

    old_org_id = str(old_org or "")
    old_staff_id = str(old_staff or "")
    old_division_id = str(old_division or "")

    def _is_distinct(candidate: Dict[str, Any]) -> bool:
        org_id = str((candidate.get("organization") or {}).get("id") or "")
        staff_id = str((candidate.get("staff") or {}).get("id") or "")
        division_id = str((candidate.get("division") or {}).get("id") or "")
        return org_id != old_org_id or staff_id != old_staff_id or division_id != old_division_id

    def _first_distinct(
        pool: List[Dict[str, Any]],
        required_org_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        for item in pool:
            if not _is_distinct(item):
                continue
            if required_org_id:
                org_id = str((item.get("organization") or {}).get("id") or "")
                if org_id != str(required_org_id):
                    continue
            return item
        return None

    next_candidate = _first_distinct(candidates, required_org_id=old_org_id or resolved_preferred_org)
    if not next_candidate:
        next_candidate = _first_distinct(candidates)

    # If same-organization candidates are exhausted, broaden to all orgs while preserving reject exclusions.
    if not next_candidate and resolved_preferred_org:
        expanded_candidates = _scored_candidates(preferred_org=None)
        next_candidate = _first_distinct(expanded_candidates, required_org_id=old_org_id)
        if not next_candidate:
            next_candidate = _first_distinct(expanded_candidates)

    if not next_candidate:
        return None

    next_org = next_candidate.get("organization")
    next_staff = next_candidate.get("staff")
    next_division = next_candidate.get("division")

    transfer_assignment_workload(
        db,
        old_org_id=old_org,
        old_division_id=old_division,
        old_staff_id=old_staff,
        new_org_id=next_org.get("id"),
        new_division_id=next_division.get("id") if next_division else None,
        new_staff_id=next_staff.get("id") if next_staff else None,
        sos_id=str(sos.id),
    )

    sos.assigned_organization = next_org.get("id")
    sos.assigned_to = next_staff.get("id") if next_staff else None
    sos.assigned_division = next_division.get("id") if next_division else None
    sos.status = "Pending Assignment"
    sos.assignment_time = datetime.utcnow()
    sos.updated_at = datetime.utcnow()

    db.add(
        TicketUpdate(
            ticket_id=str(sos.id),
            updated_by="system",
            field_name="assignment_reassigned",
            old_value=str(old_staff) if old_staff else None,
            new_value=str(sos.assigned_to) if sos.assigned_to else None,
            notes=(
                f"Auto-reassigned with excluded_staff={sorted(resolved_exclude_staff)}; "
                f"preferred_org={resolved_preferred_org or 'none'}"
            ),
        )
    )

    # Start new response-window timer
    asyncio.create_task(auto_reassign_emergency(sos_id))
    db.commit()
    db.refresh(sos)
    return {
        "sos_id": str(sos.id),
        "organization_id": sos.assigned_organization,
        "organization_name": next_org.get("name") if next_org else None,
        "staff_id": sos.assigned_to,
        "staff_name": next_staff.get("name") if next_staff else None,
        "division_id": sos.assigned_division,
        "division_name": next_division.get("name") if next_division else None,
        "status": sos.status,
    }

async def reassign_to_next_best_team_background(sos_id: str):
    db = SessionLocal()
    try:
        await reassign_to_next_best_team(sos_id, db)
    finally:
        db.close()


async def _expire_and_reassign_if_needed(sos: SOSRequest, db: Session) -> Optional[Dict[str, Any]]:
    if sos.status != "Pending Assignment" or not sos.assignment_time:
        return None

    elapsed = (datetime.utcnow() - sos.assignment_time).total_seconds()
    if elapsed <= ASSIGNMENT_RESPONSE_WINDOW_SECONDS:
        return None

    return await reassign_to_next_best_team(
        str(sos.id),
        db,
        exclude_staff_ids=[str(sos.assigned_to)] if sos.assigned_to else [],
        preferred_org_id=str(sos.assigned_organization) if sos.assigned_organization else None,
    )

@router.get("/coordination-dashboard")
async def get_emergency_coordination_dashboard(
    latitude: float = Query(..., description="Emergency location latitude"),
    longitude: float = Query(..., description="Emergency location longitude"),
    emergency_type: str = Query(..., description="Type of emergency"),
    people_affected: int = Query(..., description="Number of people affected"),
    db: Session = Depends(get_db)
):
    """Get comprehensive emergency response coordination dashboard"""
    
    # Find nearest available organizations
    organizations = db.query(Organization).filter(
        Organization.status == "Active",
        Organization.current_load < Organization.capacity
    ).all()
    
    nearest_orgs = []
    for org in organizations:
        org_lat, org_lon = infer_telangana_anchor(f"{org.name or ''} {org.address or ''}")
        distance = calculate_distance(latitude, longitude, org_lat, org_lon)
        
        nearest_orgs.append({
            "id": str(org.id),
            "name": org.name,
            "type": org.type,
            "category": org.category,
            "distance_km": round(distance, 2),
            "available_capacity": org.capacity - org.current_load,
            "current_load": org.current_load,
            "total_capacity": org.capacity,
            "contact_person": org.contact_person,
            "contact_phone": org.contact_phone,
            "estimated_response_time": round(distance * 3, 1)  # 3 min per km
        })
    
    # Sort by distance
    nearest_orgs.sort(key=lambda x: x["distance_km"])
    
    # Find available staff by emergency type
    staff_query = db.query(Staff).filter(
        Staff.status == "Active",
        Staff.availability == "Available"
    )
    
    if emergency_type.lower() in ["medical", "medical emergency"]:
        staff_query = staff_query.filter(Staff.skills.ilike("%medical%"))
    elif emergency_type.lower() in ["rescue", "needs rescue", "fire"]:
        staff_query = staff_query.filter(Staff.skills.ilike("%rescue%"))
    
    available_staff = staff_query.all()
    
    nearest_staff = []
    for staff in available_staff:
        staff_lat, staff_lon = infer_telangana_anchor(staff.current_location or staff.name)
        distance = calculate_distance(latitude, longitude, staff_lat, staff_lon)
        
        nearest_staff.append({
            "id": str(staff.id),
            "name": staff.name,
            "role": staff.role,
            "skills": staff.skills,
            "organization": staff.organization_id,
            "distance_km": round(distance, 2),
            "estimated_arrival_time": round(distance * 2, 1)  # 2 min per km
        })
    
    # Sort by distance
    nearest_staff.sort(key=lambda x: x["distance_km"])
    
    # Find nearby shelters
    shelters = db.query(Shelter).filter(
        Shelter.status == "Active",
        (Shelter.capacity - Shelter.current_occupancy) >= people_affected
    ).all()
    
    nearby_shelters = []
    for shelter in shelters:
        distance = calculate_distance(latitude, longitude, shelter.latitude, shelter.longitude)
        available_capacity = shelter.capacity - shelter.current_occupancy
        
        nearby_shelters.append({
            "id": str(shelter.id),
            "name": shelter.name,
            "distance_km": round(distance, 2),
            "available_capacity": available_capacity,
            "can_accommodate": available_capacity >= people_affected,
            "facilities": shelter.facilities,
            "contact_person": shelter.contact_person,
            "contact_phone": shelter.contact_phone
        })
    
    # Sort by distance
    nearby_shelters.sort(key=lambda x: x["distance_km"])
    
    # Find nearby hospitals
    hospitals = db.query(Hospital).filter(
        Hospital.available_beds > 0
    ).all()
    
    nearby_hospitals = []
    for hospital in hospitals:
        distance = calculate_distance(latitude, longitude, hospital.latitude, hospital.longitude)
        
        nearby_hospitals.append({
            "id": str(hospital.id),
            "name": hospital.name,
            "distance_km": round(distance, 2),
            "available_beds": hospital.available_beds,
            "available_icu": hospital.available_icu,
            "specialties": hospital.specialties,
            "emergency_services": hospital.emergency_services,
            "contact_phone": hospital.contact_phone
        })
    
    # Sort by distance
    nearby_hospitals.sort(key=lambda x: x["distance_km"])
    
    # Find emergency supplies
    emergency_supplies = []
    supply_types = ["Life Jackets", "First Aid Kits", "Emergency Food", "Water", "Blankets"]
    
    for supply_type in supply_types:
        centers = db.query(ResourceCenter).filter(
            ResourceCenter.type.ilike(f"%{supply_type}%"),
            ResourceCenter.current_stock > 0
        ).all()
        
        for center in centers:
            distance = calculate_distance(latitude, longitude, center.latitude, center.longitude)
            
            emergency_supplies.append({
                "id": str(center.id),
                "name": center.name,
                "type": center.type,
                "distance_km": round(distance, 2),
                "available_stock": center.current_stock,
                "contact_person": center.contact_person,
                "contact_phone": center.contact_phone
            })
    
    # Sort by distance
    emergency_supplies.sort(key=lambda x: x["distance_km"])
    
    return {
        "emergency_location": {
            "latitude": latitude,
            "longitude": longitude,
            "type": emergency_type,
            "people_affected": people_affected
        },
        "response_coordination": {
            "nearest_organizations": nearest_orgs[:5],  # Top 5 nearest
            "available_staff": nearest_staff[:10],     # Top 10 nearest
            "nearby_shelters": nearby_shelters[:5],    # Top 5 nearest
            "nearby_hospitals": nearby_hospitals[:5],  # Top 5 nearest
            "emergency_supplies": emergency_supplies[:10]  # Top 10 nearest
        },
        "response_recommendations": {
            "primary_organization": nearest_orgs[0] if nearest_orgs else None,
            "primary_staff": nearest_staff[0] if nearest_staff else None,
            "primary_shelter": nearby_shelters[0] if nearby_shelters else None,
            "primary_hospital": nearby_hospitals[0] if nearby_hospitals else None,
            "estimated_total_response_time": round(
                (nearest_orgs[0]["estimated_response_time"] if nearest_orgs else 0) +
                (nearest_staff[0]["estimated_arrival_time"] if nearest_staff else 0), 1
            )
        }
    }

@router.get("/smart-assignment")
async def get_smart_assignment(
    sos_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get smart assignment recommendations for an SOS request"""
    sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS request not found")

    if sos.status in ["Pending", "Pending Assignment"] and not sos.assigned_to:
        reassigned_missing = await reassign_to_next_best_team(str(sos.id), db)
        if reassigned_missing:
            sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
            if not sos:
                raise HTTPException(status_code=404, detail="SOS request not found")

    reassigned = await _expire_and_reassign_if_needed(sos, db)
    if reassigned:
        sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
        if not sos:
            raise HTTPException(status_code=404, detail="SOS request not found")

    organizations = db.query(Organization).all()
    staff_members = db.query(Staff).all()
    divisions = db.query(Division).all()

    triage = triage_sos(
        text=sos.text,
        voice_transcript=None,
        people=sos.people,
        category_hint=sos.category,
        place=sos.place,
    )
    scored = recommend_assignment(sos, organizations, staff_members, divisions, triage_context=triage)

    assigned_org = None
    assigned_staff = None
    assigned_division = None
    if sos.assigned_organization:
        assigned_org = db.query(Organization).filter(Organization.id == sos.assigned_organization).first()
    if sos.assigned_to:
        assigned_staff = db.query(Staff).filter(Staff.id == sos.assigned_to).first()
    if sos.assigned_division:
        assigned_division = db.query(Division).filter(Division.id == sos.assigned_division).first()

    # Compute assignment response window status.
    time_remaining = None
    if sos.status == "Pending Assignment" and sos.assignment_time:
        elapsed = (datetime.utcnow() - sos.assignment_time).total_seconds()
        time_remaining = max(0, ASSIGNMENT_RESPONSE_WINDOW_SECONDS - elapsed)

    can_act, resolved_staff = _can_responder_act_on_sos(current_user, sos, db)

    return {
        "sos_request": {
            "id": str(sos.id),
            "status": sos.status,
            "category": sos.category,
            "priority": sos.priority,
            "people": sos.people,
            "location": f"{sos.latitude}, {sos.longitude}",
            "assigned_organization": str(sos.assigned_organization) if sos.assigned_organization else None,
            "assigned_staff": str(sos.assigned_to) if sos.assigned_to else None,
            "assigned_division": str(sos.assigned_division) if sos.assigned_division else None,
            "assigned_organization_name": assigned_org.name if assigned_org else None,
            "assigned_staff_name": assigned_staff.name if assigned_staff else None,
            "assigned_division_name": assigned_division.name if assigned_division else None,
        },
        "recommended_assignment": scored["recommended_assignment"],
        "assignment_score": scored["assignment_score"],
        "ai_assignment_context": scored.get("assignment_context", {}),
        "auto_reassignment": reassigned,
        "user_permissions": {
            "can_accept_reject_complete": can_act,
            "resolved_staff_id": str(resolved_staff.id) if resolved_staff else None,
            "resolved_staff_name": resolved_staff.name if resolved_staff else None,
        },
        "response_metrics": {
            "acceptance_time_remaining": round(time_remaining, 1) if time_remaining is not None else None
        },
    }

@router.post("/assign-emergency")
async def assign_emergency(
    assignment_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Assign emergency to organization with one-minute acceptance window."""
    try:
        sos_id = assignment_data.get("sos_id")
        organization_id = assignment_data.get("organization_id")
        staff_id = assignment_data.get("staff_id")
        division_id = assignment_data.get("division_id")
        
        if not sos_id:
            raise HTTPException(status_code=400, detail="SOS ID is required")
        
        sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
        if not sos:
            raise HTTPException(status_code=404, detail="SOS request not found")

        # Ensure we always assign both organization and staff.
        if not organization_id or not staff_id:
            triage = triage_sos(
                text=sos.text,
                voice_transcript=None,
                people=sos.people,
                category_hint=sos.category,
                place=sos.place,
            )
            scored = recommend_assignment(
                sos,
                db.query(Organization).all(),
                db.query(Staff).all(),
                db.query(Division).all(),
                triage_context=triage,
                assignment_constraints={"preferred_org_id": organization_id} if organization_id else None,
            )
            recommended = scored.get("recommended_assignment", {})
            rec_org = recommended.get("organization") or {}
            rec_staff = recommended.get("staff") or {}
            rec_division = recommended.get("division") or {}
            organization_id = organization_id or rec_org.get("id")
            staff_id = staff_id or rec_staff.get("id")
            division_id = division_id or rec_division.get("id")

        if not organization_id or not staff_id:
            raise HTTPException(
                status_code=422,
                detail="No valid organization/staff available for assignment",
            )

        staff_record = db.query(Staff).filter(Staff.id == staff_id).first()
        if not staff_record:
            raise HTTPException(status_code=404, detail="Assigned staff not found")

        if str(staff_record.organization_id) != str(organization_id):
            organization_id = staff_record.organization_id

        if not division_id and staff_record.division_id:
            division_id = staff_record.division_id

        was_uncommitted_pending = (
            sos.status == "Pending"
            and sos.assignment_time is None
            and not any([sos.assigned_organization, sos.assigned_to, sos.assigned_division])
        )
        old_org = sos.assigned_organization
        old_staff = sos.assigned_to
        old_division = sos.assigned_division

        # Update SOS request with pending assignment
        sos.assigned_organization = organization_id
        sos.assigned_to = staff_id
        sos.assigned_division = division_id
        sos.status = "Pending Assignment"
        sos.assignment_time = datetime.utcnow()
        sos.updated_at = datetime.utcnow()

        transfer_assignment_workload(
            db,
            old_org_id=None if was_uncommitted_pending else old_org,
            old_division_id=None if was_uncommitted_pending else old_division,
            old_staff_id=None if was_uncommitted_pending else old_staff,
            new_org_id=organization_id,
            new_division_id=division_id,
            new_staff_id=staff_id,
            sos_id=str(sos.id),
        )

        db.commit()
        assigned_org = db.query(Organization).filter(Organization.id == organization_id).first()
        assigned_staff = db.query(Staff).filter(Staff.id == staff_id).first()
        assigned_division = db.query(Division).filter(Division.id == division_id).first() if division_id else None
        
        # Start one-minute timer for auto-reassignment
        background_tasks.add_task(auto_reassign_emergency, sos_id)
        
        return {
            "message": "Emergency assigned successfully. Assigned responder has 1 minute to accept.",
            "sos_id": sos_id,
            "assigned_organization": organization_id,
            "assigned_organization_name": assigned_org.name if assigned_org else None,
            "assigned_staff": staff_id,
            "assigned_staff_name": assigned_staff.name if assigned_staff else None,
            "assigned_division": division_id,
            "assigned_division_name": assigned_division.name if assigned_division else None,
            "acceptance_deadline": (datetime.utcnow() + timedelta(seconds=ASSIGNMENT_RESPONSE_WINDOW_SECONDS)).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error assigning emergency: {str(e)}")

@router.post("/accept-assignment")
async def accept_assignment(
    acceptance_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("responder")),
):
    """Organization accepts emergency assignment"""
    try:
        sos_id = acceptance_data.get("sos_id")
        organization_id = acceptance_data.get("organization_id")
        estimated_completion = acceptance_data.get("estimated_completion")
        
        sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
        if not sos:
            raise HTTPException(status_code=404, detail="SOS request not found")

        can_act, staff = _can_responder_act_on_sos(current_user, sos, db)
        if not can_act:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Only assigned responder staff can accept this emergency. "
                    f"Assigned staff id={sos.assigned_to}"
                ),
            )
        
        # Allow first-time assignment acceptance from Pending state.
        if not sos.assigned_organization:
            sos.assigned_organization = organization_id

        if sos.assigned_organization != organization_id:
            raise HTTPException(status_code=400, detail="Organization not assigned to this emergency")
        
        if sos.status not in ["Pending Assignment", "Pending"]:
            raise HTTPException(status_code=400, detail="Emergency not eligible for acceptance")
        
        # Check if still within the one-minute response window.
        if sos.status == "Pending" and not sos.assignment_time:
            sos.assignment_time = datetime.utcnow()

        if sos.assignment_time and (
            datetime.utcnow() - sos.assignment_time
        ).total_seconds() > ASSIGNMENT_RESPONSE_WINDOW_SECONDS:
            reassigned = await reassign_to_next_best_team(
                str(sos.id),
                db,
                exclude_staff_ids=[str(sos.assigned_to)] if sos.assigned_to else [],
                preferred_org_id=str(sos.assigned_organization) if sos.assigned_organization else None,
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Acceptance window expired. Emergency reassigned immediately.",
                    "reassigned_to": reassigned,
                },
            )
        
        parsed_completion = None
        if estimated_completion:
            if isinstance(estimated_completion, datetime):
                parsed_completion = estimated_completion
            else:
                try:
                    parsed_completion = datetime.fromisoformat(str(estimated_completion))
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid estimated_completion datetime format")

        # Accept assignment
        transfer_assignment_workload(
            db,
            old_org_id=sos.assigned_organization,
            old_division_id=sos.assigned_division,
            old_staff_id=sos.assigned_to,
            new_org_id=sos.assigned_organization,
            new_division_id=sos.assigned_division,
            new_staff_id=sos.assigned_to,
            sos_id=str(sos.id),
        )

        sos.status = "In Progress"
        sos.estimated_completion = parsed_completion
        sos.accepted_at = datetime.utcnow()
        sos.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": "Assignment accepted successfully",
            "sos_id": sos_id,
            "status": "In Progress",
            "estimated_completion": estimated_completion
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error accepting assignment: {str(e)}")

@router.post("/reject-assignment")
async def reject_assignment(
    rejection_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("responder")),
):
    """Organization rejects emergency assignment"""
    try:
        sos_id = rejection_data.get("sos_id")
        organization_id = rejection_data.get("organization_id")
        rejection_reason = rejection_data.get("reason", "No reason provided")
        
        sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
        if not sos:
            raise HTTPException(status_code=404, detail="SOS request not found")

        can_act, staff = _can_responder_act_on_sos(current_user, sos, db)
        if not can_act:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Only assigned responder staff can reject this emergency. "
                    f"Assigned staff id={sos.assigned_to}"
                ),
            )
        
        if sos.assigned_organization != organization_id:
            raise HTTPException(status_code=400, detail="Organization not assigned to this emergency")

        rejected_staff_id = str(sos.assigned_to or "").strip()
        if rejected_staff_id:
            db.add(
                TicketUpdate(
                    ticket_id=str(sos.id),
                    updated_by=str(staff.id) if staff else "system",
                    field_name="assignment_rejection",
                    old_value=rejected_staff_id,
                    new_value=rejection_reason,
                    notes=f"Rejected by organization {organization_id}",
                )
            )
            db.flush()
        
        reassigned = await reassign_to_next_best_team(
            str(sos.id),
            db,
            exclude_staff_ids=[str(sos.assigned_to)] if sos.assigned_to else [],
            preferred_org_id=str(sos.assigned_organization) if sos.assigned_organization else None,
        )
        if not reassigned:
            raise HTTPException(status_code=422, detail="No replacement responder could be assigned")

        return {
            "message": "Assignment rejected and reassigned immediately.",
            "sos_id": sos_id,
            "status": "Pending Assignment",
            "rejection_reason": rejection_reason,
            "reassigned_to": reassigned,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error rejecting assignment: {str(e)}")

@router.post("/deploy-response-team")
async def deploy_response_team(
    deployment_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Deploy a response team to an emergency"""
    try:
        sos_id = deployment_data.get("sos_id")
        organization_id = deployment_data.get("organization_id")
        staff_ids = deployment_data.get("staff_ids", [])
        estimated_completion = deployment_data.get("estimated_completion")
        
        if not sos_id:
            raise HTTPException(status_code=400, detail="SOS ID is required")
        
        sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
        if not sos:
            raise HTTPException(status_code=404, detail="SOS request not found")

        old_org = sos.assigned_organization
        old_staff = sos.assigned_to
        old_division = sos.assigned_division
        primary_staff = staff_ids[0] if staff_ids else old_staff

        # Update SOS request
        sos.assigned_organization = organization_id
        sos.assigned_to = primary_staff
        sos.status = "In Progress"
        sos.estimated_completion = estimated_completion
        sos.updated_at = datetime.utcnow()

        transfer_assignment_workload(
            db,
            old_org_id=old_org,
            old_division_id=old_division,
            old_staff_id=old_staff,
            new_org_id=organization_id,
            new_division_id=old_division,
            new_staff_id=primary_staff,
            sos_id=str(sos.id),
        )

        # Update additional staff availability
        for staff_id in staff_ids:
            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            if staff:
                staff.availability = "Busy"
                staff.current_location = f"Responding to SOS {sos_id}"
        
        db.commit()
        
        return {
            "message": "Response team deployed successfully",
            "sos_id": sos_id,
            "assigned_organization": organization_id,
            "deployed_staff": staff_ids,
            "estimated_completion": estimated_completion
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deploying response team: {str(e)}")


@router.post("/complete-emergency")
async def complete_emergency(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("responder")),
):
    """
    Mark incident complete and release assignment workload counters.
    """
    sos_id = payload.get("sos_id")
    resolution_notes = payload.get("resolution_notes")
    if not sos_id:
        raise HTTPException(status_code=400, detail="sos_id is required")

    sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS request not found")

    can_act, staff = _can_responder_act_on_sos(current_user, sos, db)
    if not can_act:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Only assigned responder staff can complete this emergency. "
                f"Assigned staff id={sos.assigned_to}"
            ),
        )

    if sos.status != "Done":
        release_assignment_workload(db, sos.assigned_organization, sos.assigned_division, sos.assigned_to)

    sos.status = "Done"
    sos.actual_completion = datetime.utcnow()
    sos.updated_at = datetime.utcnow()
    if resolution_notes:
        sos.notes = f"{(sos.notes or '').strip()} | completion_notes={resolution_notes}".strip(" |")

    db.commit()
    return {
        "message": "Emergency marked as completed",
        "sos_id": sos_id,
        "status": sos.status,
        "completed_at": sos.actual_completion.isoformat() if sos.actual_completion else None,
    }

@router.get("/response-status/{sos_id}")
async def get_response_status(sos_id: str, db: Session = Depends(get_db)):
    """Get current response status for an SOS request"""
    sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS request not found")
    
    # Get assigned organization details
    organization = None
    if sos.assigned_organization:
        organization = db.query(Organization).filter(Organization.id == sos.assigned_organization).first()
    
    # Get assigned staff details
    assigned_staff = None
    if sos.assigned_to:
        assigned_staff = db.query(Staff).filter(Staff.id == sos.assigned_to).first()
    
    # Get assigned division details
    assigned_division = None
    if sos.assigned_division:
        assigned_division = db.query(Division).filter(Division.id == sos.assigned_division).first()
    
    # Calculate response metrics
    response_time = None
    if sos.assigned_to and sos.created_at:
        response_time = (sos.updated_at - sos.created_at).total_seconds() / 60  # minutes
    
    # Calculate time remaining for acceptance
    time_remaining = None
    if sos.status == "Pending Assignment" and sos.assignment_time:
        elapsed = (datetime.utcnow() - sos.assignment_time).total_seconds()
        time_remaining = max(0, ASSIGNMENT_RESPONSE_WINDOW_SECONDS - elapsed)
    
    return {
        "sos_request": {
            "id": str(sos.id),
            "status": sos.status,
            "priority": sos.priority,
            "category": sos.category,
            "people": sos.people,
            "created_at": sos.created_at,
            "updated_at": sos.updated_at
        },
        "response_team": {
            "organization": {
                "id": str(organization.id),
                "name": organization.name,
                "type": organization.type,
                "contact_person": organization.contact_person,
                "contact_phone": organization.contact_phone
            } if organization else None,
            "assigned_staff": {
                "id": str(assigned_staff.id),
                "name": assigned_staff.name,
                "role": assigned_staff.role,
                "skills": assigned_staff.skills,
                "availability": assigned_staff.availability,
                "current_location": assigned_staff.current_location
            } if assigned_staff else None,
            "assigned_division": {
                "id": str(assigned_division.id),
                "name": assigned_division.name,
                "type": assigned_division.type
            } if assigned_division else None
        },
        "response_metrics": {
            "response_time_minutes": round(response_time, 1) if response_time else None,
            "estimated_completion": sos.estimated_completion,
            "actual_completion": sos.actual_completion,
            "is_overdue": sos.estimated_completion and datetime.utcnow() > sos.estimated_completion,
            "acceptance_time_remaining": round(time_remaining, 1) if time_remaining is not None else None
        }
    }

@router.get("/emergency-summary")
async def get_emergency_summary(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get summary of all active emergencies and response status"""
    query = db.query(SOSRequest).filter(
        SOSRequest.status.in_(["Pending", "In Progress", "Pending Assignment"])
    )
    if (current_user.role or "").lower() == "responder":
        resolved_staff = resolve_responder_staff(current_user, db)
        if not resolved_staff:
            query = query.filter(SOSRequest.id == "__none__")
        else:
            query = query.filter(SOSRequest.assigned_to == resolved_staff.id)

    active_sos = query.order_by(SOSRequest.priority.desc(), SOSRequest.created_at.asc()).all()
    
    emergency_summary = []
    for sos in active_sos:
        if sos.status in ["Pending", "Pending Assignment"] and not sos.assigned_to:
            reassigned_missing = await reassign_to_next_best_team(str(sos.id), db)
            if reassigned_missing:
                sos = db.query(SOSRequest).filter(SOSRequest.id == sos.id).first() or sos

        reassigned = await _expire_and_reassign_if_needed(sos, db)
        if reassigned:
            sos = db.query(SOSRequest).filter(SOSRequest.id == sos.id).first() or sos

        # Get assignment details
        organization = None
        if sos.assigned_organization:
            organization = db.query(Organization).filter(Organization.id == sos.assigned_organization).first()
        
        assigned_staff = None
        if sos.assigned_to:
            assigned_staff = db.query(Staff).filter(Staff.id == sos.assigned_to).first()
        
        assigned_division = None
        if sos.assigned_division:
            assigned_division = db.query(Division).filter(Division.id == sos.assigned_division).first()
        
        # Calculate age
        age_hours = (datetime.utcnow() - sos.created_at).total_seconds() / 3600
        
        # Calculate acceptance time remaining
        acceptance_time_remaining = None
        if sos.status == "Pending Assignment" and sos.assignment_time:
            elapsed = (datetime.utcnow() - sos.assignment_time).total_seconds()
            acceptance_time_remaining = max(0, ASSIGNMENT_RESPONSE_WINDOW_SECONDS - elapsed)
        
        emergency_summary.append({
            "id": str(sos.id),
            "status": sos.status,
            "priority": sos.priority,
            "category": sos.category,
            "people": sos.people,
            "place": sos.place,
            "age_hours": round(age_hours, 1),
            "assigned_organization": organization.name if organization else "Unassigned",
            "assigned_staff": assigned_staff.name if assigned_staff else "Unassigned",
            "assigned_division": assigned_division.name if assigned_division else "Unassigned",
            "is_overdue": sos.estimated_completion and datetime.utcnow() > sos.estimated_completion,
            "acceptance_time_remaining": round(acceptance_time_remaining, 1) if acceptance_time_remaining is not None else None
        })
    
    return {
        "total_active_emergencies": len(emergency_summary),
        "by_priority": {
            "critical": len([e for e in emergency_summary if e["priority"] == 5]),
            "high": len([e for e in emergency_summary if e["priority"] == 4]),
            "medium": len([e for e in emergency_summary if e["priority"] == 3]),
            "low": len([e for e in emergency_summary if e["priority"] <= 2])
        },
        "by_status": {
            "pending": len([e for e in emergency_summary if e["status"] == "Pending"]),
            "pending_assignment": len([e for e in emergency_summary if e["status"] == "Pending Assignment"]),
            "in_progress": len([e for e in emergency_summary if e["status"] == "In Progress"])
        },
        "overdue_emergencies": len([e for e in emergency_summary if e["is_overdue"]]),
        "emergencies": emergency_summary
    }
