from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from database import get_db, Division, Organization, Staff, SOSRequest
from models import DivisionCreate, DivisionUpdate, DivisionResponse
from routes.auth_routes import require_roles
import uuid
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/", response_model=DivisionResponse)
async def create_division(
    division_data: DivisionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Create a new division"""
    try:
        # Verify organization exists
        org = db.query(Organization).filter(Organization.id == division_data.organization_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        db_division = Division(
            name=division_data.name,
            organization_id=division_data.organization_id,
            type=division_data.type,
            description=division_data.description,
            capacity=division_data.capacity
        )
        
        db.add(db_division)
        db.commit()
        db.refresh(db_division)
        
        return db_division
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating division: {str(e)}")

@router.get("/", response_model=List[DivisionResponse])
async def get_divisions(
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    type: Optional[str] = Query(None, description="Filter by division type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """Get divisions with filtering options"""
    query = db.query(Division)
    
    if organization_id:
        query = query.filter(Division.organization_id == organization_id)
    if type:
        query = query.filter(Division.type == type)
    if status:
        query = query.filter(Division.status == status)
    
    return query.all()

@router.get("/{division_id}", response_model=DivisionResponse)
async def get_division(division_id: str, db: Session = Depends(get_db)):
    """Get a specific division by ID"""
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    
    return division

@router.put("/{division_id}", response_model=DivisionResponse)
async def update_division(
    division_id: str,
    division_update: DivisionUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Update division information"""
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    
    update_data = division_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(division, field, value)
    
    # Update status based on load
    if division.current_load >= division.capacity:
        division.status = "Overloaded"
    elif division.current_load > 0:
        division.status = "Active"
    else:
        division.status = "Available"
    
    db.commit()
    db.refresh(division)
    
    return division

@router.delete("/{division_id}")
async def delete_division(
    division_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin")),
):
    """Delete a division (admin only)"""
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    
    db.delete(division)
    db.commit()
    
    return {"message": "Division deleted successfully"}

@router.get("/{division_id}/workload")
async def get_division_workload(division_id: str, db: Session = Depends(get_db)):
    """Get current workload for a division"""
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    
    # Get staff in this division
    staff_count = db.query(func.count(Staff.id)).filter(Staff.division_id == division_id).scalar()
    active_staff = db.query(func.count(Staff.id)).filter(
        Staff.division_id == division_id,
        Staff.status == "Active"
    ).scalar()
    
    # Get assigned tickets
    assigned_tickets = db.query(func.count(SOSRequest.id)).filter(
        SOSRequest.assigned_division == division_id,
        SOSRequest.status.in_(["Pending", "In Progress"])
    ).scalar()
    
    # Get completed tickets today
    today = datetime.utcnow().date()
    completed_today = db.query(func.count(SOSRequest.id)).filter(
        SOSRequest.assigned_division == division_id,
        SOSRequest.status == "Done",
        func.date(SOSRequest.actual_completion) == today
    ).scalar()
    
    # Get completed tickets this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    completed_week = db.query(func.count(SOSRequest.id)).filter(
        SOSRequest.assigned_division == division_id,
        SOSRequest.status == "Done",
        SOSRequest.actual_completion >= week_ago
    ).scalar()
    
    return {
        "division_id": division_id,
        "division_name": division.name,
        "total_staff": staff_count,
        "active_staff": active_staff,
        "assigned_tickets": assigned_tickets,
        "completed_today": completed_today,
        "completed_week": completed_week,
        "current_load": division.current_load,
        "capacity": division.capacity,
        "utilization_rate": round(division.current_load / division.capacity * 100, 2) if division.capacity > 0 else 0
    }

@router.get("/overview/stats")
async def get_divisions_overview(db: Session = Depends(get_db)):
    """Get overview statistics for all divisions"""
    try:
        total_divisions = db.query(func.count(Division.id)).scalar()
        active_divisions = db.query(func.count(Division.id)).filter(Division.status == "Active").scalar()
        total_capacity = db.query(func.sum(Division.capacity)).scalar() or 0
        current_load = db.query(func.sum(Division.current_load)).scalar() or 0
        
        # Type breakdown
        type_counts = db.query(
            Division.type,
            func.count(Division.id).label('count'),
            func.sum(Division.capacity).label('total_capacity')
        ).group_by(Division.type).all()
        
        # Organization breakdown
        org_counts = db.query(
            Organization.name,
            func.count(Division.id).label('count'),
            func.sum(Division.capacity).label('total_capacity')
        ).join(Division, Organization.id == Division.organization_id).group_by(Organization.name).all()
        
        return {
            "total_divisions": total_divisions,
            "active_divisions": active_divisions,
            "total_capacity": total_capacity,
            "current_load": current_load,
            "utilization_rate": round(current_load / total_capacity * 100, 2) if total_capacity > 0 else 0,
            "type_breakdown": [
                {
                    "type": item.type,
                    "count": item.count,
                    "total_capacity": item.total_capacity or 0
                }
                for item in type_counts
            ],
            "organization_breakdown": [
                {
                    "organization": item.name,
                    "count": item.count,
                    "total_capacity": item.total_capacity or 0
                }
                for item in org_counts
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching division overview: {str(e)}")

@router.get("/{division_id}/staff")
async def get_division_staff(division_id: str, db: Session = Depends(get_db)):
    """Get all staff members in a specific division"""
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    
    staff_members = db.query(Staff).filter(Staff.division_id == division_id).all()
    
    result = []
    for staff in staff_members:
        # Get workload for each staff member
        assigned_tickets = db.query(func.count(SOSRequest.id)).filter(
            SOSRequest.assigned_to == staff.id,
            SOSRequest.status.in_(["Pending", "In Progress"])
        ).scalar()
        
        result.append({
            "id": staff.id,
            "name": staff.name,
            "role": staff.role,
            "availability": staff.availability,
            "current_location": staff.current_location,
            "assigned_tickets": assigned_tickets,
            "skills": staff.skills
        })
    
    return result
