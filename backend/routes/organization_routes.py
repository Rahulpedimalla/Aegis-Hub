from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from database import get_db, Organization, Division, Staff, SOSRequest
from models import OrganizationCreate, OrganizationUpdate, OrganizationResponse, OrganizationDashboardStats
from routes.auth_routes import require_roles
import uuid
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=OrganizationResponse)
async def create_organization(
    organization_data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Create a new organization"""
    try:
        db_org = Organization(
            name=organization_data.name,
            type=organization_data.type,
            category=organization_data.category,
            address=organization_data.address,
            contact_person=organization_data.contact_person,
            contact_phone=organization_data.contact_phone,
            contact_email=organization_data.contact_email,
            capacity=organization_data.capacity
        )
        
        db.add(db_org)
        db.commit()
        db.refresh(db_org)
        
        return db_org
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating organization: {str(e)}")

@router.get("/", response_model=List[OrganizationResponse])
async def get_organizations(
    type: Optional[str] = Query(None, description="Filter by organization type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """Get organizations with filtering options"""
    query = db.query(Organization)
    
    if type:
        query = query.filter(Organization.type == type)
    if category:
        query = query.filter(Organization.category == category)
    if status:
        query = query.filter(Organization.status == status)
    
    return query.all()

@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: str, db: Session = Depends(get_db)):
    """Get a specific organization by ID"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return org

@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    org_update: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Update organization information"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    update_data = org_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)
    
    # Update status based on load
    if org.current_load >= org.capacity:
        org.status = "Overloaded"
    elif org.current_load > 0:
        org.status = "Active"
    else:
        org.status = "Available"
    
    db.commit()
    db.refresh(org)
    
    return org

@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin")),
):
    """Delete an organization (admin only)"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    db.delete(org)
    db.commit()
    
    return {"message": "Organization deleted successfully"}

@router.get("/{org_id}/dashboard", response_model=OrganizationDashboardStats)
async def get_organization_dashboard(org_id: str, db: Session = Depends(get_db)):
    """Get dashboard statistics for a specific organization"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Get staff statistics
    total_staff = db.query(func.count(Staff.id)).filter(Staff.organization_id == org_id).scalar()
    active_staff = db.query(func.count(Staff.id)).filter(
        Staff.organization_id == org_id,
        Staff.status == "Active"
    ).scalar()
    
    # Get division statistics
    total_divisions = db.query(func.count(Division.id)).filter(Division.organization_id == org_id).scalar()
    active_divisions = db.query(func.count(Division.id)).filter(
        Division.organization_id == org_id,
        Division.status == "Active"
    ).scalar()
    
    # Get ticket statistics
    assigned_tickets = db.query(func.count(SOSRequest.id)).filter(
        SOSRequest.assigned_organization == org_id,
        SOSRequest.status.in_(["Pending", "In Progress"])
    ).scalar()
    
    completed_tickets = db.query(func.count(SOSRequest.id)).filter(
        SOSRequest.assigned_organization == org_id,
        SOSRequest.status == "Done"
    ).scalar()
    
    return OrganizationDashboardStats(
        organization_id=org.id,
        organization_name=org.name,
        total_staff=total_staff,
        active_staff=active_staff,
        total_divisions=total_divisions,
        active_divisions=active_divisions,
        assigned_tickets=assigned_tickets,
        completed_tickets=completed_tickets,
        current_load=org.current_load,
        capacity=org.capacity
    )

@router.get("/overview/stats")
async def get_organizations_overview(db: Session = Depends(get_db)):
    """Get overview statistics for all organizations"""
    try:
        total_organizations = db.query(func.count(Organization.id)).scalar()
        total_capacity = db.query(func.sum(Organization.capacity)).scalar() or 0
        current_load = db.query(func.sum(Organization.current_load)).scalar() or 0
        
        # Type breakdown
        type_counts = db.query(
            Organization.type,
            func.count(Organization.id).label('count'),
            func.sum(Organization.capacity).label('total_capacity')
        ).group_by(Organization.type).all()
        
        # Category breakdown
        category_counts = db.query(
            Organization.category,
            func.count(Organization.id).label('count')
        ).group_by(Organization.category).all()
        
        # Status breakdown
        status_counts = db.query(
            Organization.status,
            func.count(Organization.id).label('count')
        ).group_by(Organization.status).all()
        
        return {
            "total_organizations": total_organizations,
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
            "category_breakdown": [
                {
                    "category": item.category,
                    "count": item.count
                }
                for item in category_counts
            ],
            "status_breakdown": [
                {
                    "status": item.status,
                    "count": item.count
                }
                for item in status_counts
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching organization overview: {str(e)}")
