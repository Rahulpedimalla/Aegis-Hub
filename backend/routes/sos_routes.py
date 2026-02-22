import json
import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text
from typing import Dict, List, Optional
import math
from datetime import datetime
from types import SimpleNamespace

from database import SessionLocal, User, get_db, SOSRequest, Organization, Staff, Division, TicketUpdate, MobileIncident
from models import SOSRequestCreate, SOSRequestUpdate, SOSRequestResponse, SOSMapData, TicketUpdateCreate, SOSIntakeRequest
import uuid
from database import Shelter, Hospital
from routes.auth_routes import get_current_user, require_roles, verify_token
from services.assignment_service import recommend_assignment
from services.geo_utils import infer_telangana_anchor
from services.staff_resolution_service import resolve_responder_staff
from services.triage_service import triage_sos
from services.workload_service import release_assignment_workload, transfer_assignment_workload

router = APIRouter()


def _extract_stream_token(authorization: Optional[str], access_token: Optional[str]) -> Optional[str]:
    query_token = str(access_token or "").strip()
    if query_token:
        return query_token

    header_value = str(authorization or "").strip()
    if header_value.lower().startswith("bearer "):
        token = header_value.split(" ", 1)[1].strip()
        if token:
            return token
    return None


def _resolve_stream_user(
    db: Session,
    authorization: Optional[str],
    access_token: Optional[str],
) -> User:
    token = _extract_stream_token(authorization=authorization, access_token=access_token)
    if not token:
        raise HTTPException(status_code=401, detail="Missing stream token")

    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid stream token")

    user = (
        db.query(User)
        .filter(User.username == username, User.is_active.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if (user.role or "").lower() not in {"admin", "responder"}:
        raise HTTPException(status_code=403, detail="Access denied for stream")

    return user


def _sos_change_snapshot(db: Session) -> Dict[str, Optional[str]]:
    total_tickets = int(db.query(func.count(SOSRequest.id)).scalar() or 0)
    max_updated = db.query(func.max(SOSRequest.updated_at)).scalar()
    max_created = db.query(func.max(SOSRequest.created_at)).scalar()
    max_history_update = db.query(func.max(TicketUpdate.update_time)).scalar()

    candidates = [item for item in [max_updated, max_created, max_history_update] if item is not None]
    latest_change = max(candidates) if candidates else None
    latest_change_text = latest_change.isoformat() if latest_change else ""

    pending_count = int(db.query(func.count(SOSRequest.id)).filter(SOSRequest.status == "Pending").scalar() or 0)
    pending_assignment_count = int(
        db.query(func.count(SOSRequest.id)).filter(SOSRequest.status == "Pending Assignment").scalar() or 0
    )
    in_progress_count = int(db.query(func.count(SOSRequest.id)).filter(SOSRequest.status == "In Progress").scalar() or 0)

    fingerprint = (
        f"{total_tickets}|{latest_change_text}|{pending_count}|{pending_assignment_count}|{in_progress_count}"
    )
    return {
        "fingerprint": fingerprint,
        "latest_change_at": latest_change_text,
        "total_tickets": total_tickets,
        "pending": pending_count,
        "pending_assignment": pending_assignment_count,
        "in_progress": in_progress_count,
    }


def _to_static_media_url(request: Request, relative_path: str) -> Optional[str]:
    normalized = str(relative_path or "").replace("\\", "/").strip().lstrip("/")
    if not normalized:
        return None
    if normalized.startswith("static/"):
        normalized = normalized[len("static/"):]
    if not normalized.startswith("mobile_uploads/"):
        return None
    base = str(request.base_url).rstrip("/")
    return f"{base}/static/{normalized}"


def _mobile_incident_for_ticket(db: Session, sos: SOSRequest) -> Optional[MobileIncident]:
    filters = [MobileIncident.dispatched_ticket_id == str(sos.id)]
    if sos.external_id:
        filters.append(MobileIncident.external_id == str(sos.external_id))

    return (
        db.query(MobileIncident)
        .filter(or_(*filters))
        .order_by(MobileIncident.created_at.desc())
        .first()
    )

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

def find_nearest_organization(sos_lat, sos_lon, db: Session):
    """Find the nearest available organization for the SOS request"""
    organizations = db.query(Organization).filter(Organization.status == "Active").all()
    
    if not organizations:
        return None
    
    nearest_org = None
    min_distance = float('inf')
    
    for org in organizations:
        org_lat, org_lon = infer_telangana_anchor(f"{org.name or ''} {org.address or ''}")
        
        distance = calculate_distance(sos_lat, sos_lon, org_lat, org_lon)
        if distance < min_distance:
            min_distance = distance
            nearest_org = org
    
    return nearest_org

def find_nearest_staff(sos_lat, sos_lon, category, db: Session):
    """Find the nearest available staff member for the SOS request"""
    # Filter staff by category and availability
    if category.lower() in ["medical emergency", "medical"]:
        staff_query = db.query(Staff).filter(
            Staff.status == "Active",
            Staff.availability == "Available",
            Staff.skills.ilike("%medical%")
        )
    elif category.lower() in ["needs rescue", "fire emergency"]:
        staff_query = db.query(Staff).filter(
            Staff.status == "Active",
            Staff.availability == "Available",
            Staff.skills.ilike("%rescue%")
        )
    else:
        staff_query = db.query(Staff).filter(
            Staff.status == "Active",
            Staff.availability == "Available"
        )
    
    available_staff = staff_query.all()
    
    if not available_staff:
        return None
    
    nearest_staff = None
    min_distance = float('inf')
    
    for staff in available_staff:
        staff_lat, staff_lon = infer_telangana_anchor(staff.current_location or staff.name)
        
        distance = calculate_distance(sos_lat, sos_lon, staff_lat, staff_lon)
        if distance < min_distance:
            min_distance = distance
            nearest_staff = staff
    
    return nearest_staff


def _ensure_assignment_for_active_ticket(db: Session, sos: SOSRequest) -> None:
    """
    Ensure active tickets are not left unassigned.
    """
    if sos.status not in ["Pending", "Pending Assignment"]:
        return
    if sos.assigned_to and sos.assigned_organization:
        return

    triage = triage_sos(
        text=sos.text,
        voice_transcript=None,
        people=sos.people,
        category_hint=sos.category,
        place=sos.place,
    )
    scored = recommend_assignment(
        SimpleNamespace(latitude=sos.latitude, longitude=sos.longitude, category=triage["category"]),
        db.query(Organization).all(),
        db.query(Staff).all(),
        db.query(Division).all(),
        triage_context=triage,
    )
    recommended = scored.get("recommended_assignment", {})
    org = recommended.get("organization")
    staff = recommended.get("staff")
    division = recommended.get("division")
    if not org or not staff:
        return

    old_org = sos.assigned_organization
    old_div = sos.assigned_division
    old_staff = sos.assigned_to
    sos.assigned_organization = org.get("id")
    sos.assigned_to = staff.get("id")
    sos.assigned_division = division.get("id") if division else None
    sos.status = "Pending Assignment"
    sos.assignment_time = datetime.utcnow()
    sos.updated_at = datetime.utcnow()

    transfer_assignment_workload(
        db=db,
        old_org_id=old_org,
        old_division_id=old_div,
        old_staff_id=old_staff,
        new_org_id=sos.assigned_organization,
        new_division_id=sos.assigned_division,
        new_staff_id=sos.assigned_to,
        sos_id=str(sos.id),
    )
    db.commit()
    db.refresh(sos)

@router.post("/intake")
async def intake_sos_request(
    payload: SOSIntakeRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """
    Ingestion endpoint for future citizen/responder applications.
    Performs AI triage, assigns priority/category, and stores SOS.
    """
    try:
        triage = triage_sos(
            text=payload.text,
            voice_transcript=payload.voice_transcript,
            people=payload.people,
            category_hint=payload.category_hint,
            environmental_risk=0,
            place=payload.place,
        )

        external_id = payload.external_id or f"APP-{uuid.uuid4().hex[:10].upper()}"
        place = payload.place or "Telangana (location from app)"
        description = payload.text or payload.voice_transcript or "Emergency request from app"

        candidate_orgs = db.query(Organization).all()
        candidate_staff = db.query(Staff).all()
        candidate_divisions = db.query(Division).all()
        scored = recommend_assignment(
            SimpleNamespace(latitude=payload.latitude, longitude=payload.longitude, category=triage["category"]),
            candidate_orgs,
            candidate_staff,
            candidate_divisions,
            triage_context=triage,
        )
        recommended = scored.get("recommended_assignment", {})
        org = recommended.get("organization")
        staff = recommended.get("staff")
        division = recommended.get("division")
        auto_assigned = bool(org and staff)

        db_sos = SOSRequest(
            external_id=external_id,
            status="Pending Assignment" if auto_assigned else "Pending",
            people=triage["people"],
            longitude=payload.longitude,
            latitude=payload.latitude,
            text=description,
            place=place,
            category=triage["category"],
            priority=triage["priority"],
            assigned_organization=org["id"] if org else None,
            assigned_to=staff["id"] if staff else None,
            assigned_division=division["id"] if division else None,
            assignment_time=datetime.utcnow() if auto_assigned else None,
            notes=(
                f"source={payload.source}; triage_source={triage.get('source','rules')}; "
                f"division_type={triage.get('division_type')}; urgency={triage['urgency_level']}; "
                f"confidence={triage['confidence']}"
            ),
            timestamp=datetime.utcnow(),
        )

        db.add(db_sos)
        db.flush()
        if auto_assigned:
            transfer_assignment_workload(
                db=db,
                old_org_id=None,
                old_division_id=None,
                old_staff_id=None,
                new_org_id=db_sos.assigned_organization,
                new_division_id=db_sos.assigned_division,
                new_staff_id=db_sos.assigned_to,
                sos_id=str(db_sos.id),
            )
        db.commit()
        db.refresh(db_sos)

        return {
            "message": "SOS received and triaged",
            "triage": triage,
            "sos_id": str(db_sos.id),
            "external_id": db_sos.external_id,
            "recommended_org": str(db_sos.assigned_organization) if db_sos.assigned_organization else None,
            "recommended_staff": str(db_sos.assigned_to) if db_sos.assigned_to else None,
            "recommended_division": str(db_sos.assigned_division) if db_sos.assigned_division else None,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing SOS intake: {str(e)}")

@router.post("/", response_model=SOSRequestResponse)
async def create_sos_request(
    sos_data: SOSRequestCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Create a new SOS request from n8n workflow with smart assignment"""
    try:
        triage = triage_sos(
            text=sos_data.text,
            voice_transcript=None,
            people=sos_data.people,
            category_hint=sos_data.category,
            environmental_risk=0,
            place=sos_data.place,
        )

        candidate_orgs = db.query(Organization).all()
        candidate_staff = db.query(Staff).all()
        candidate_divisions = db.query(Division).all()
        scored = recommend_assignment(
            SimpleNamespace(latitude=sos_data.latitude, longitude=sos_data.longitude, category=triage["category"]),
            candidate_orgs,
            candidate_staff,
            candidate_divisions,
            triage_context=triage,
        )
        recommended = scored.get("recommended_assignment", {})
        org = recommended.get("organization")
        staff = recommended.get("staff")
        division = recommended.get("division")
        auto_assigned = bool(org and staff)
        
        db_sos = SOSRequest(
            external_id=sos_data.external_id,
            status="Pending Assignment" if auto_assigned else "Pending",
            people=triage["people"],
            longitude=sos_data.longitude,
            latitude=sos_data.latitude,
            text=sos_data.text,
            place=sos_data.place,
            category=triage["category"],
            priority=triage["priority"],
            assigned_organization=org["id"] if org else None,
            assigned_to=staff["id"] if staff else None,
            assigned_division=division["id"] if division else None,
            assignment_time=datetime.utcnow() if auto_assigned else None,
            notes=(
                f"triage_source={triage.get('source','rules')}; division_type={triage.get('division_type')}; "
                f"urgency={triage['urgency_level']}; confidence={triage['confidence']}"
            ),
            timestamp=datetime.utcnow()
        )
        
        db.add(db_sos)
        db.flush()
        if auto_assigned:
            transfer_assignment_workload(
                db=db,
                old_org_id=None,
                old_division_id=None,
                old_staff_id=None,
                new_org_id=db_sos.assigned_organization,
                new_division_id=db_sos.assigned_division,
                new_staff_id=db_sos.assigned_to,
                sos_id=str(db_sos.id),
            )
        db.commit()
        db.refresh(db_sos)
        
        # Create ticket update record
        if org or staff or division:
            update_record = TicketUpdate(
                ticket_id=str(db_sos.id),
                updated_by=staff["id"] if staff else "system",
                field_name="initial_assignment",
                new_value=(
                    f"Assigned to {org['name'] if org else 'No org'} - "
                    f"{staff['name'] if staff else 'No staff'} - "
                    f"{division['name'] if division else 'No division'}"
                ),
                notes=f"Automatic assignment based on AI triage ({triage.get('source', 'rules')})"
            )
            db.add(update_record)
            db.commit()
        
        return db_sos
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating SOS request: {str(e)}")

@router.get("/", response_model=List[SOSRequestResponse])
async def get_sos_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    region: Optional[str] = Query(None, description="Filter by Telangana zone (South, Central, North)"),
    priority: Optional[int] = Query(None, ge=1, le=5, description="Filter by priority"),
    limit: int = Query(100, le=1000, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get SOS requests with filtering options"""
    query = db.query(SOSRequest)

    if (current_user.role or "").lower() == "responder":
        resolved_staff = resolve_responder_staff(current_user, db)
        if not resolved_staff:
            query = query.filter(SOSRequest.id == "__none__")
        else:
            query = query.filter(SOSRequest.assigned_to == resolved_staff.id)
    
    if status:
        query = query.filter(SOSRequest.status == status)
    if category:
        query = query.filter(SOSRequest.category.ilike(f"%{category}%"))
    if priority:
        query = query.filter(SOSRequest.priority == priority)
    
    # Region filtering based on coordinates
    if region:
        if region.lower() == "south":
            query = query.filter(SOSRequest.longitude >= 77.0, SOSRequest.longitude <= 78.4)
        elif region.lower() == "central":
            query = query.filter(SOSRequest.longitude >= 78.4, SOSRequest.longitude <= 79.6)
        elif region.lower() == "north":
            query = query.filter(SOSRequest.longitude >= 79.6, SOSRequest.longitude <= 81.0)
    
    query = query.order_by(SOSRequest.priority.desc(), SOSRequest.created_at.desc())
    query = query.offset(offset).limit(limit)

    records = query.all()
    for sos in records:
        _ensure_assignment_for_active_ticket(db, sos)
    return records

@router.get("/map", response_model=List[SOSMapData])
async def get_sos_map_data(
    bounds: Optional[str] = Query(None, description="Map bounds: north,south,east,west"),
    db: Session = Depends(get_db)
):
    """Get SOS data for map visualization"""
    query = db.query(SOSRequest).filter(SOSRequest.status != "Done")
    
    if bounds:
        try:
            north, south, east, west = map(float, bounds.split(','))
            # Filter by bounding box
            query = query.filter(
                SOSRequest.latitude <= north,
                SOSRequest.latitude >= south,
                SOSRequest.longitude <= east,
                SOSRequest.longitude >= west
            )
        except ValueError:
            pass
    
    sos_requests = query.all()
    
    return [
        SOSMapData(
            id=str(sos.id),
            longitude=sos.longitude,
            latitude=sos.latitude,
            status=sos.status,
            category=sos.category,
            priority=sos.priority,
            people=sos.people,
            place=sos.place
        )
        for sos in sos_requests
    ]


@router.get("/events/stream")
async def stream_sos_events(
    request: Request,
    access_token: Optional[str] = Query(default=None, description="Bearer token for EventSource authentication"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    Server-Sent Events stream for SOS ticket changes.
    Emits `tickets_changed` whenever ticket list/assignment/status changes.
    """
    _resolve_stream_user(db=db, authorization=authorization, access_token=access_token)

    async def event_generator():
        heartbeat_ticks = 0
        last_fingerprint = ""

        while True:
            if await request.is_disconnected():
                break

            try:
                stream_db = SessionLocal()
                try:
                    snapshot = _sos_change_snapshot(stream_db)
                finally:
                    stream_db.close()

                if snapshot["fingerprint"] != last_fingerprint:
                    last_fingerprint = snapshot["fingerprint"]
                    payload = {
                        "type": "tickets_changed",
                        "server_time": datetime.utcnow().isoformat(),
                        **snapshot,
                    }
                    yield f"event: tickets_changed\ndata: {json.dumps(payload)}\n\n"
                elif heartbeat_ticks % 10 == 0:
                    heartbeat = {"type": "heartbeat", "server_time": datetime.utcnow().isoformat()}
                    yield f"event: heartbeat\ndata: {json.dumps(heartbeat)}\n\n"

                heartbeat_ticks += 1
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@router.get("/{sos_id}", response_model=SOSRequestResponse)
async def get_sos_request(
    sos_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get a specific SOS request by ID"""
    sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS request not found")

    _ensure_assignment_for_active_ticket(db, sos)

    if (current_user.role or "").lower() == "responder":
        resolved_staff = resolve_responder_staff(current_user, db)
        if not resolved_staff or str(sos.assigned_to or "") != str(resolved_staff.id):
            raise HTTPException(status_code=403, detail="Access denied for this ticket")
    
    return sos


@router.get("/{sos_id}/media")
async def get_ticket_media(
    sos_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return voice/media evidence linked to a ticket (if created via mobile pipeline)."""
    sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS request not found")

    if (current_user.role or "").lower() == "responder":
        resolved_staff = resolve_responder_staff(current_user, db)
        if not resolved_staff or str(sos.assigned_to or "") != str(resolved_staff.id):
            raise HTTPException(status_code=403, detail="Access denied for this ticket")

    incident = _mobile_incident_for_ticket(db, sos)
    if not incident:
        return {
            "ticket_id": str(sos.id),
            "incident_id": None,
            "voice_transcript": None,
            "audio_files": [],
            "media_manifest": {},
        }

    try:
        media_manifest = json.loads(incident.media_manifest or "{}")
        if not isinstance(media_manifest, dict):
            media_manifest = {}
    except Exception:
        media_manifest = {}

    raw_audio_items = media_manifest.get("audio") or []
    audio_files = []
    for item in raw_audio_items:
        if not isinstance(item, dict):
            continue
        relative_path = str(item.get("relative_path") or "").strip()
        audio_url = _to_static_media_url(request, relative_path)
        if not audio_url:
            continue
        audio_files.append(
            {
                "file_name": item.get("file_name"),
                "content_type": item.get("content_type"),
                "size_bytes": item.get("size_bytes"),
                "relative_path": relative_path,
                "url": audio_url,
            }
        )

    return {
        "ticket_id": str(sos.id),
        "incident_id": incident.external_id or incident.id,
        "voice_transcript": incident.voice_transcript,
        "audio_files": audio_files,
        "media_manifest": media_manifest,
    }

@router.put("/{sos_id}", response_model=SOSRequestResponse)
async def update_sos_request(
    sos_id: str,
    sos_update: SOSRequestUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Update an SOS request status and assignment"""
    # Try to find by string ID first, then by UUID
    sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
    
    if not sos:
        try:
            sos_uuid = uuid.UUID(sos_id)
            sos = db.query(SOSRequest).filter(SOSRequest.id == sos_uuid).first()
        except ValueError:
            pass
    
    if not sos:
        raise HTTPException(status_code=404, detail="SOS request not found")

    if (current_user.role or "").lower() == "responder":
        resolved_staff = resolve_responder_staff(current_user, db)
        if not resolved_staff or str(sos.assigned_to or "") != str(resolved_staff.id):
            raise HTTPException(status_code=403, detail="Only assigned responder can update this ticket")
    
    # Store old values for update history
    old_status = sos.status
    old_assigned_to = sos.assigned_to
    old_assigned_org = sos.assigned_organization
    old_assigned_div = sos.assigned_division
    old_notes = sos.notes
    
    # Update fields
    update_data = sos_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sos, field, value)

    sos.updated_at = datetime.utcnow()
    
    completed_now = sos.status == "Done" and old_status != "Done"
    cancelled_now = sos.status == "Cancelled" and old_status != "Cancelled"
    reactivated = old_status in ["Done", "Cancelled"] and sos.status not in ["Done", "Cancelled"]

    # Ensure workload counters follow assignment lifecycle.
    if completed_now or cancelled_now:
        release_assignment_workload(db, sos.assigned_organization, sos.assigned_division, sos.assigned_to)
    elif reactivated and (sos.assigned_organization or sos.assigned_division or sos.assigned_to):
        transfer_assignment_workload(
            db,
            old_org_id=None,
            old_division_id=None,
            old_staff_id=None,
            new_org_id=sos.assigned_organization,
            new_division_id=sos.assigned_division,
            new_staff_id=sos.assigned_to,
            sos_id=str(sos.id),
        )
    elif (
        old_assigned_org != sos.assigned_organization
        or old_assigned_div != sos.assigned_division
        or old_assigned_to != sos.assigned_to
    ):
        transfer_assignment_workload(
            db,
            old_org_id=old_assigned_org,
            old_division_id=old_assigned_div,
            old_staff_id=old_assigned_to,
            new_org_id=sos.assigned_organization,
            new_division_id=sos.assigned_division,
            new_staff_id=sos.assigned_to,
            sos_id=str(sos.id),
        )

    # Update completion time if status changed to Done
    if sos.status == "Done" and old_status != "Done":
        sos.actual_completion = datetime.utcnow()
    
    db.commit()
    db.refresh(sos)
    
    # Create update history records
    updates_to_record = []
    
    if sos.status != old_status:
        updates_to_record.append(TicketUpdate(
            ticket_id=str(sos.id),
            updated_by="system",  # In production, get from authenticated user
            field_name="status",
            old_value=old_status,
            new_value=sos.status,
            notes=sos_update.notes if hasattr(sos_update, 'notes') else None
        ))
    
    if sos.assigned_to != old_assigned_to:
        updates_to_record.append(TicketUpdate(
            ticket_id=str(sos.id),
            updated_by="system",
            field_name="assigned_to",
            old_value=old_assigned_to,
            new_value=sos.assigned_to,
            notes="Staff assignment updated"
        ))
    
    if sos.notes != old_notes:
        updates_to_record.append(TicketUpdate(
            ticket_id=str(sos.id),
            updated_by="system",
            field_name="notes",
            old_value=old_notes,
            new_value=sos.notes,
            notes="Notes updated"
        ))
    
    # Add update records to database
    for update_record in updates_to_record:
        db.add(update_record)
    
    if updates_to_record:
        db.commit()
    
    return sos

@router.delete("/{sos_id}")
async def delete_sos_request(
    sos_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin")),
):
    """Delete an SOS request (admin only)"""
    sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS request not found")

    if sos.status not in ["Done", "Cancelled"]:
        release_assignment_workload(db, sos.assigned_organization, sos.assigned_division, sos.assigned_to)
    
    db.delete(sos)
    db.commit()
    
    return {"message": "SOS request deleted successfully"}

@router.get("/stats/summary")
async def get_sos_summary(db: Session = Depends(get_db)):
    """Get summary statistics for SOS requests"""
    total = db.query(func.count(SOSRequest.id)).scalar()
    pending = db.query(func.count(SOSRequest.id)).filter(SOSRequest.status == "Pending").scalar()
    in_progress = db.query(func.count(SOSRequest.id)).filter(SOSRequest.status == "In Progress").scalar()
    completed = db.query(func.count(SOSRequest.id)).filter(SOSRequest.status == "Done").scalar()
    total_people = db.query(func.sum(SOSRequest.people)).scalar() or 0
    
    return {
        "total_requests": total,
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
        "total_people_affected": total_people
    }

@router.get("/stats/by-category")
async def get_sos_by_category(db: Session = Depends(get_db)):
    """Get SOS requests grouped by category"""
    result = db.query(
        SOSRequest.category,
        func.count(SOSRequest.id).label('count'),
        func.sum(SOSRequest.people).label('people_affected')
    ).group_by(SOSRequest.category).all()
    
    return [
        {
            "category": item.category,
            "count": item.count,
            "people_affected": item.people_affected or 0
        }
        for item in result
    ]

@router.get("/stats/by-region")
async def get_sos_by_region(db: Session = Depends(get_db)):
    """Get SOS requests grouped by region"""
    regions = [
        ("South Telangana", 77.0, 78.4),
        ("Central Telangana", 78.4, 79.6),
        ("North Telangana", 79.6, 81.0)
    ]
    
    region_stats = []
    for region_name, west_lon, east_lon in regions:
        count = db.query(func.count(SOSRequest.id)).filter(
            SOSRequest.longitude >= west_lon,
            SOSRequest.longitude <= east_lon
        ).scalar()
        
        people = db.query(func.sum(SOSRequest.people)).filter(
            SOSRequest.longitude >= west_lon,
            SOSRequest.longitude <= east_lon
        ).scalar() or 0
        
        region_stats.append({
            "region": region_name,
            "sos_count": count,
            "people_affected": people
        })
    
    return region_stats

@router.get("/{sos_id}/updates")
async def get_ticket_updates(sos_id: str, db: Session = Depends(get_db)):
    """Get update history for a specific SOS request"""
    updates = db.query(TicketUpdate).filter(TicketUpdate.ticket_id == str(sos_id)).order_by(TicketUpdate.update_time.desc()).all()
    return updates

@router.post("/{sos_id}/assign")
async def assign_sos_request(
    sos_id: str,
    assignment_data: dict,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Manually assign an SOS request to organization/staff"""
    sos = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS request not found")
    
    old_org = sos.assigned_organization
    old_div = sos.assigned_division
    old_staff = sos.assigned_to
    was_uncommitted_pending = (
        sos.status == "Pending"
        and sos.assignment_time is None
        and not any([sos.assigned_organization, sos.assigned_to, sos.assigned_division])
    )

    # Update assignment
    if 'organization_id' in assignment_data:
        sos.assigned_organization = assignment_data['organization_id']
    
    if 'staff_id' in assignment_data:
        sos.assigned_to = assignment_data['staff_id']

    if 'division_id' in assignment_data:
        sos.assigned_division = assignment_data['division_id']
    
    if 'estimated_completion' in assignment_data:
        sos.estimated_completion = assignment_data['estimated_completion']

    if sos.status == "Pending":
        sos.status = "Pending Assignment"
        sos.assignment_time = datetime.utcnow()

    transfer_assignment_workload(
        db,
        old_org_id=None if was_uncommitted_pending else old_org,
        old_division_id=None if was_uncommitted_pending else old_div,
        old_staff_id=None if was_uncommitted_pending else old_staff,
        new_org_id=sos.assigned_organization,
        new_division_id=sos.assigned_division,
        new_staff_id=sos.assigned_to,
        sos_id=str(sos.id),
    )
    
    sos.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sos)
    
    # Create update record
    update_record = TicketUpdate(
        ticket_id=str(sos.id),
        updated_by="system",
        field_name="manual_assignment",
        new_value=f"Assigned to org: {assignment_data.get('organization_id', 'None')}, staff: {assignment_data.get('staff_id', 'None')}",
        notes="Manual assignment by operator"
    )
    db.add(update_record)
    db.commit()
    
    return sos

@router.get("/{sos_id}/nearest-facilities")
async def get_nearest_facilities(
    sos_id: str,
    db: Session = Depends(get_db)
):
    """Get nearest available shelter and hospital for an SOS request"""
    try:
        # Find the SOS request
        sos_request = None
        try:
            # Try to find by UUID first
            sos_request = db.query(SOSRequest).filter(SOSRequest.id == sos_id).first()
        except:
            # If UUID fails, try to find by string ID
            sos_request = db.query(SOSRequest).filter(SOSRequest.external_id == sos_id).first()
        
        if not sos_request:
            raise HTTPException(status_code=404, detail="SOS request not found")
        
        sos_lat = sos_request.latitude
        sos_lon = sos_request.longitude
        
        # Find nearest shelter with available capacity
        shelters = db.query(Shelter).filter(
            Shelter.status == "Active",
            Shelter.current_occupancy < Shelter.capacity
        ).all()
        
        nearest_shelter = None
        min_shelter_distance = float('inf')
        
        for shelter in shelters:
            distance = calculate_distance(sos_lat, sos_lon, shelter.latitude, shelter.longitude)
            if distance < min_shelter_distance:
                min_shelter_distance = distance
                nearest_shelter = {
                    "id": str(shelter.id),
                    "name": shelter.name,
                    "address": shelter.address,
                    "latitude": shelter.latitude,
                    "longitude": shelter.longitude,
                    "distance_km": round(distance, 2),
                    "available_capacity": shelter.capacity - shelter.current_occupancy,
                    "total_capacity": shelter.capacity,
                    "current_occupancy": shelter.current_occupancy,
                    "facilities": shelter.facilities,
                    "contact_person": shelter.contact_person,
                    "contact_phone": shelter.contact_phone,
                    "google_maps_url": f"https://www.google.com/maps/dir/{sos_lat},{sos_lon}/{shelter.latitude},{shelter.longitude}"
                }
        
        # Find nearest hospital with available beds
        hospitals = db.query(Hospital).filter(
            Hospital.available_beds > 0
        ).all()
        
        nearest_hospital = None
        min_hospital_distance = float('inf')
        
        for hospital in hospitals:
            distance = calculate_distance(sos_lat, sos_lon, hospital.latitude, hospital.longitude)
            if distance < min_hospital_distance:
                min_hospital_distance = distance
                nearest_hospital = {
                    "id": str(hospital.id),
                    "name": hospital.name,
                    "address": hospital.address,
                    "latitude": hospital.latitude,
                    "longitude": hospital.longitude,
                    "distance_km": round(distance, 2),
                    "available_beds": hospital.available_beds,
                    "total_beds": hospital.total_beds,
                    "available_icu": hospital.available_icu,
                    "total_icu": hospital.icu_beds,
                    "contact_phone": hospital.contact_phone,
                    "google_maps_url": f"https://www.google.com/maps/dir/{sos_lat},{sos_lon}/{hospital.latitude},{hospital.longitude}"
                }
        
        return {
            "sos_request": {
                "id": str(sos_request.id),
                "external_id": sos_request.external_id,
                "category": sos_request.category,
                "place": sos_request.place,
                "latitude": sos_request.latitude,
                "longitude": sos_request.longitude,
                "people": sos_request.people
            },
            "nearest_shelter": nearest_shelter,
            "nearest_hospital": nearest_hospital,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding nearest facilities: {str(e)}")
