from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from database import get_db, Staff, Organization, Division, SOSRequest
from models import StaffCreate, StaffUpdate, StaffResponse
from routes.auth_routes import require_roles
import uuid
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/", response_model=StaffResponse)
async def create_staff(
    staff_data: StaffCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Create a new staff member"""
    try:
        # Verify organization exists
        org = db.query(Organization).filter(Organization.id == staff_data.organization_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Verify division exists if provided
        if staff_data.division_id:
            div = db.query(Division).filter(Division.id == staff_data.division_id).first()
            if not div:
                raise HTTPException(status_code=404, detail="Division not found")
        
        db_staff = Staff(
            name=staff_data.name,
            organization_id=staff_data.organization_id,
            division_id=staff_data.division_id,
            role=staff_data.role,
            skills=staff_data.skills,
            contact_phone=staff_data.contact_phone,
            contact_email=staff_data.contact_email,
            current_location=staff_data.current_location
        )
        
        db.add(db_staff)
        db.commit()
        db.refresh(db_staff)
        
        return db_staff
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating staff member: {str(e)}")

@router.get("/", response_model=List[StaffResponse])
async def get_staff(
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    division_id: Optional[str] = Query(None, description="Filter by division"),
    role: Optional[str] = Query(None, description="Filter by role"),
    availability: Optional[str] = Query(None, description="Filter by availability"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """Get staff members with filtering options"""
    query = db.query(Staff)
    
    if organization_id:
        query = query.filter(Staff.organization_id == organization_id)
    if division_id:
        query = query.filter(Staff.division_id == division_id)
    if role:
        query = query.filter(Staff.role == role)
    if availability:
        query = query.filter(Staff.availability == availability)
    if status:
        query = query.filter(Staff.status == status)
    
    return query.all()

@router.get("/{staff_id}", response_model=StaffResponse)
async def get_staff_member(staff_id: str, db: Session = Depends(get_db)):
    """Get a specific staff member by ID"""
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    return staff

@router.put("/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: str,
    staff_update: StaffUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Update staff member information"""
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    update_data = staff_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(staff, field, value)
    
    db.commit()
    db.refresh(staff)
    
    return staff

@router.delete("/{staff_id}")
async def delete_staff(
    staff_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin")),
):
    """Delete a staff member (admin only)"""
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    db.delete(staff)
    db.commit()
    
    return {"message": "Staff member deleted successfully"}

@router.get("/{staff_id}/workload")
async def get_staff_workload(staff_id: str, db: Session = Depends(get_db)):
    """Get current workload for a staff member"""
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Get assigned tickets
    assigned_tickets = db.query(func.count(SOSRequest.id)).filter(
        SOSRequest.assigned_to == staff_id,
        SOSRequest.status.in_(["Pending", "In Progress"])
    ).scalar()
    
    # Get completed tickets today
    today = datetime.utcnow().date()
    completed_today = db.query(func.count(SOSRequest.id)).filter(
        SOSRequest.assigned_to == staff_id,
        SOSRequest.status == "Done",
        func.date(SOSRequest.actual_completion) == today
    ).scalar()
    
    # Get completed tickets this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    completed_week = db.query(func.count(SOSRequest.id)).filter(
        SOSRequest.assigned_to == staff_id,
        SOSRequest.status == "Done",
        SOSRequest.actual_completion >= week_ago
    ).scalar()
    
    return {
        "staff_id": staff_id,
        "staff_name": staff.name,
        "assigned_tickets": assigned_tickets,
        "completed_today": completed_today,
        "completed_week": completed_week,
        "availability": staff.availability,
        "current_location": staff.current_location
    }

@router.get("/overview/stats")
async def get_staff_overview(db: Session = Depends(get_db)):
    """Get overview statistics for all staff"""
    try:
        total_staff = db.query(func.count(Staff.id)).scalar()
        active_staff = db.query(func.count(Staff.id)).filter(Staff.status == "Active").scalar()
        available_staff = db.query(func.count(Staff.id)).filter(Staff.availability == "Available").scalar()
        
        # Role breakdown
        role_counts = db.query(
            Staff.role,
            func.count(Staff.id).label('count')
        ).group_by(Staff.role).all()
        
        # Availability breakdown
        availability_counts = db.query(
            Staff.availability,
            func.count(Staff.id).label('count')
        ).group_by(Staff.availability).all()
        
        # Organization breakdown
        org_counts = db.query(
            Organization.name,
            func.count(Staff.id).label('count')
        ).join(Staff, Organization.id == Staff.organization_id).group_by(Organization.name).all()
        
        return {
            "total_staff": total_staff,
            "active_staff": active_staff,
            "available_staff": available_staff,
            "utilization_rate": round((total_staff - available_staff) / total_staff * 100, 2) if total_staff > 0 else 0,
            "role_breakdown": [
                {
                    "role": item.role,
                    "count": item.count
                }
                for item in role_counts
            ],
            "availability_breakdown": [
                {
                    "availability": item.availability,
                    "count": item.count
                }
                for item in availability_counts
            ],
            "organization_breakdown": [
                {
                    "organization": item.name,
                    "count": item.count
                }
                for item in org_counts
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching staff overview: {str(e)}")

@router.get("/overview/available")
async def get_available_staff(
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    division_id: Optional[str] = Query(None, description="Filter by division"),
    role: Optional[str] = Query(None, description="Filter by role"),
    db: Session = Depends(get_db)
):
    """Get available staff members for assignment"""
    query = db.query(Staff).filter(
        Staff.status == "Active",
        Staff.availability == "Available"
    )
    
    if organization_id:
        query = query.filter(Staff.organization_id == organization_id)
    if division_id:
        query = query.filter(Staff.division_id == division_id)
    if role:
        query = query.filter(Staff.role == role)
    
    available_staff = query.all()
    
    # Get workload for each available staff member
    result = []
    for staff in available_staff:
        assigned_tickets = db.query(func.count(SOSRequest.id)).filter(
            SOSRequest.assigned_to == staff.id,
            SOSRequest.status.in_(["Pending", "In Progress"])
        ).scalar()
        
        result.append({
            "id": staff.id,
            "name": staff.name,
            "role": staff.role,
            "organization_id": staff.organization_id,
            "division_id": staff.division_id,
            "current_location": staff.current_location,
            "assigned_tickets": assigned_tickets,
            "skills": staff.skills
        })
    
    return result
