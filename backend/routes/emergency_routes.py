from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import math
from datetime import datetime, timedelta
import asyncio
import uuid

from database import get_db, SessionLocal, SOSRequest, Organization, Staff, Division, Shelter, Hospital, ResourceCenter
from models import SOSRequestResponse
from routes.auth_routes import get_current_user, require_roles
from services.assignment_service import recommend_assignment
from services.geo_utils import infer_telangana_anchor
from services.triage_service import triage_sos
from services.workload_service import release_assignment_workload, transfer_assignment_workload

router = APIRouter()

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def _normalize_person(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _resolve_responder_staff(current_user, db: Session) -> Optional[Staff]:
    """
    Best-effort mapping of authenticated responder user to a staff record.
    Priority:
    1) username-to-name normalization match
    2) unique staff in user's division
    """
    username = (current_user.username or "").strip()
    username_norm = _normalize_person(username.replace(".", " "))

    active_staff = db.query(Staff).filter(Staff.status == "Active").all()
    exact_matches = [s for s in active_staff if _normalize_person(s.name or "") == username_norm]
    if len(exact_matches) == 1:
        return exact_matches[0]

    if current_user.division_id:
        by_division = [
            s for s in active_staff
            if str(s.division_id or "") == str(current_user.division_id)
        ]
        if len(by_division) == 1:
            return by_division[0]

    return None


def _can_responder_act_on_sos(current_user, sos: SOSRequest, db: Session) -> tuple[bool, Optional[Staff]]:
    if (current_user.role or "").lower() != "responder":
        return False, None

    staff = _resolve_responder_staff(current_user, db)
    if not staff:
        return False, None

    if not sos.assigned_to:
        return False, staff

    return str(sos.assigned_to) == str(staff.id), staff

async def auto_reassign_emergency(sos_id: str):
    """Automatically reassign emergency after 5 minutes if not accepted"""
    await asyncio.sleep(300)  # Wait 5 minutes

    db = SessionLocal()
    try:
        # Check if the emergency is still pending assignment
        sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
        if sos and sos.status == "Pending Assignment":
            # Auto-reassign to next best team
            await reassign_to_next_best_team(sos_id, db)
    finally:
        db.close()

async def reassign_to_next_best_team(sos_id: str, db: Session):
    """Reassign emergency to the next best available team"""
    sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
    if not sos:
        return

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
    scored = recommend_assignment(
        sos,
        db.query(Organization).all(),
        db.query(Staff).all(),
        db.query(Division).all(),
        triage_context=triage,
    )
    recommended = scored.get("recommended_assignment", {})

    candidate_orgs = []
    if recommended.get("organization"):
        candidate_orgs.append(recommended["organization"])
    candidate_orgs.extend(recommended.get("alternatives", {}).get("organizations", []))

    next_org = next((org for org in candidate_orgs if org and org.get("id") != old_org), None)
    if not next_org:
        return

    next_staff = recommended.get("staff")
    next_division = recommended.get("division")

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

    # Start new 5-minute timer
    asyncio.create_task(auto_reassign_emergency(sos_id))
    db.commit()

async def reassign_to_next_best_team_background(sos_id: str):
    db = SessionLocal()
    try:
        await reassign_to_next_best_team(sos_id, db)
    finally:
        db.close()

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

    # Compute assignment response window status.
    time_remaining = None
    if sos.status == "Pending Assignment" and sos.assignment_time:
        elapsed = (datetime.utcnow() - sos.assignment_time).total_seconds()
        time_remaining = max(0, 300 - elapsed)

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
        },
        "recommended_assignment": scored["recommended_assignment"],
        "assignment_score": scored["assignment_score"],
        "ai_assignment_context": scored.get("assignment_context", {}),
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
    """Assign emergency to organization with 5-minute acceptance window"""
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

        was_uncommitted_pending = sos.status == "Pending" and sos.assignment_time is None
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
        
        # Start 5-minute timer for auto-reassignment
        background_tasks.add_task(auto_reassign_emergency, sos_id)
        
        return {
            "message": "Emergency assigned successfully. Organization has 5 minutes to accept.",
            "sos_id": sos_id,
            "assigned_organization": organization_id,
            "assigned_staff": staff_id,
            "assigned_division": division_id,
            "acceptance_deadline": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
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
        
        # Check if within 5-minute window
        if sos.status == "Pending" and not sos.assignment_time:
            sos.assignment_time = datetime.utcnow()

        if sos.assignment_time and (datetime.utcnow() - sos.assignment_time).total_seconds() > 300:
            raise HTTPException(status_code=400, detail="Acceptance window expired. Emergency will be reassigned.")
        
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
    background_tasks: BackgroundTasks,
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
        
        # Reject assignment and release resources.
        old_org = sos.assigned_organization
        old_staff = sos.assigned_to
        old_division = sos.assigned_division

        release_assignment_workload(db, old_org, old_division, old_staff)

        sos.status = "Pending"
        sos.assigned_organization = None
        sos.assigned_to = None
        sos.assigned_division = None
        sos.assignment_time = None
        sos.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Immediately reassign to next best team
        background_tasks.add_task(reassign_to_next_best_team_background, sos_id)
        
        return {
            "message": "Assignment rejected. Emergency will be reassigned to next best team.",
            "sos_id": sos_id,
            "status": "Pending",
            "rejection_reason": rejection_reason
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
        time_remaining = max(0, 300 - elapsed)  # 5 minutes = 300 seconds
    
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
            "acceptance_time_remaining": round(time_remaining, 1) if time_remaining else None
        }
    }

@router.get("/emergency-summary")
async def get_emergency_summary(db: Session = Depends(get_db)):
    """Get summary of all active emergencies and response status"""
    active_sos = db.query(SOSRequest).filter(
        SOSRequest.status.in_(["Pending", "In Progress", "Pending Assignment"])
    ).order_by(SOSRequest.priority.desc(), SOSRequest.created_at.asc()).all()
    
    emergency_summary = []
    for sos in active_sos:
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
            acceptance_time_remaining = max(0, 300 - elapsed)
        
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
            "acceptance_time_remaining": round(acceptance_time_remaining, 1) if acceptance_time_remaining else None
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
