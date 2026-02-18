from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime

from database import get_db, SOSRequest, Shelter, Hospital, ResourceCenter, Organization, Staff
from models import DashboardStats, RegionStats

router = APIRouter()

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get comprehensive dashboard statistics"""
    try:
        # SOS Statistics
        total_sos = db.query(func.count(SOSRequest.id)).scalar()
        pending_sos = db.query(func.count(SOSRequest.id)).filter(SOSRequest.status == "Pending").scalar()
        in_progress_sos = db.query(func.count(SOSRequest.id)).filter(SOSRequest.status == "In Progress").scalar()
        completed_sos = db.query(func.count(SOSRequest.id)).filter(SOSRequest.status == "Done").scalar()
        total_people = db.query(func.sum(SOSRequest.people)).scalar() or 0
        
        # Shelter Statistics
        total_shelter_capacity = db.query(func.sum(Shelter.capacity)).scalar() or 0
        current_shelter_occupancy = db.query(func.sum(Shelter.current_occupancy)).scalar() or 0
        available_shelter_capacity = total_shelter_capacity - current_shelter_occupancy
        
        # Hospital Statistics
        total_hospital_beds = db.query(func.sum(Hospital.total_beds)).scalar() or 0
        available_hospital_beds = db.query(func.sum(Hospital.available_beds)).scalar() or 0
        
        # Organization and Staff Statistics
        total_organizations = db.query(func.count(Organization.id)).scalar()
        total_staff = db.query(func.count(Staff.id)).scalar()
        active_staff = db.query(func.count(Staff.id)).filter(Staff.status == "Active").scalar()
        
        return DashboardStats(
            total_sos=total_sos,
            pending_sos=pending_sos,
            in_progress_sos=in_progress_sos,
            completed_sos=completed_sos,
            total_people_affected=total_people,
            total_shelter_capacity=total_shelter_capacity,
            available_shelter_capacity=available_shelter_capacity,
            total_hospital_beds=total_hospital_beds,
            available_hospital_beds=available_hospital_beds,
            total_organizations=total_organizations,
            total_staff=total_staff,
            active_staff=active_staff
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard stats: {str(e)}")

@router.get("/regions", response_model=List[RegionStats])
async def get_region_stats(db: Session = Depends(get_db)):
    """Get statistics by Telangana zones (South, Central, North)."""
    try:
        regions = [
            ("South Telangana", 77.0, 78.4),
            ("Central Telangana", 78.4, 79.6),
            ("North Telangana", 79.6, 81.0)
        ]
        
        region_stats = []
        for region_name, west_lon, east_lon in regions:
            # SOS count and people affected
            sos_count = db.query(func.count(SOSRequest.id)).filter(
                SOSRequest.longitude >= west_lon,
                SOSRequest.longitude <= east_lon
            ).scalar()
            
            people_affected = db.query(func.sum(SOSRequest.people)).filter(
                SOSRequest.longitude >= west_lon,
                SOSRequest.longitude <= east_lon
            ).scalar() or 0
            
            # Shelter capacity in region
            shelter_capacity = db.query(func.sum(Shelter.capacity)).filter(
                Shelter.longitude >= west_lon,
                Shelter.longitude <= east_lon
            ).scalar() or 0
            
            shelter_available = db.query(func.sum(Shelter.capacity - Shelter.current_occupancy)).filter(
                Shelter.longitude >= west_lon,
                Shelter.longitude <= east_lon
            ).scalar() or 0
            
            region_stats.append(RegionStats(
                region=region_name,
                sos_count=sos_count,
                people_affected=people_affected,
                shelter_capacity=shelter_capacity,
                shelter_available=shelter_available
            ))
        
        return region_stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching region stats: {str(e)}")

@router.get("/recent-activity")
async def get_recent_activity(db: Session = Depends(get_db), limit: int = 10):
    """Get recent SOS requests and updates"""
    try:
        recent_sos = db.query(SOSRequest).order_by(
            SOSRequest.updated_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": str(sos.id),
                "type": "sos_request",
                "status": sos.status,
                "category": sos.category,
                "people": sos.people,
                "place": sos.place,
                "description": f"{sos.category} at {sos.place} ({sos.people} people) is {sos.status}",
                "timestamp": sos.updated_at,
                "priority": sos.priority
            }
            for sos in recent_sos
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching recent activity: {str(e)}")

@router.get("/critical-alerts")
async def get_critical_alerts(db: Session = Depends(get_db)):
    """Get critical alerts that need immediate attention"""
    try:
        # High priority pending SOS requests
        critical_sos = db.query(SOSRequest).filter(
            SOSRequest.status == "Pending",
            SOSRequest.priority >= 4
        ).order_by(SOSRequest.priority.desc(), SOSRequest.created_at.asc()).limit(20).all()
        
        # Shelters at capacity
        full_shelters = db.query(Shelter).filter(
            Shelter.current_occupancy >= Shelter.capacity * 0.9
        ).limit(10).all()
        
        # Hospitals with low bed availability
        low_bed_hospitals = db.query(Hospital).filter(
            Hospital.available_beds <= Hospital.total_beds * 0.1
        ).limit(10).all()
        
        alerts = []

        for sos in critical_sos:
            alerts.append({
                "id": str(sos.id),
                "title": f"Critical SOS: {sos.category}",
                "description": f"{sos.people} people affected at {sos.place}",
                "timestamp": sos.created_at,
                "severity": "critical"
            })

        for shelter in full_shelters:
            alerts.append({
                "id": str(shelter.id),
                "title": f"Shelter Near Capacity: {shelter.name}",
                "description": f"{shelter.current_occupancy}/{shelter.capacity} occupied",
                "timestamp": datetime.utcnow(),
                "severity": "high"
            })

        for hospital in low_bed_hospitals:
            alerts.append({
                "id": str(hospital.id),
                "title": f"Low Beds: {hospital.name}",
                "description": f"{hospital.available_beds}/{hospital.total_beds} beds available",
                "timestamp": datetime.utcnow(),
                "severity": "high"
            })

        alerts.sort(key=lambda x: x["timestamp"], reverse=True)
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching critical alerts: {str(e)}")

@router.get("/resource-overview")
async def get_resource_overview(db: Session = Depends(get_db)):
    """Get overview of available resources"""
    try:
        # Resource centers by type
        resource_types = db.query(
            ResourceCenter.type,
            func.count(ResourceCenter.id).label('count')
        ).group_by(ResourceCenter.type).all()
        
        # Total shelters and hospitals
        total_shelters = db.query(func.count(Shelter.id)).scalar()
        total_hospitals = db.query(func.count(Hospital.id)).scalar()
        
        # Available capacity
        total_shelter_capacity = db.query(func.sum(Shelter.capacity)).scalar() or 0
        current_shelter_occupancy = db.query(func.sum(Shelter.current_occupancy)).scalar() or 0
        
        total_hospital_beds = db.query(func.sum(Hospital.total_beds)).scalar() or 0
        available_hospital_beds = db.query(func.sum(Hospital.available_beds)).scalar() or 0
        
        return {
            "resource_centers": [
                {
                    "type": item.type,
                    "count": item.count
                }
                for item in resource_types
            ],
            "shelters": {
                "total": total_shelters,
                "total_capacity": total_shelter_capacity,
                "current_occupancy": current_shelter_occupancy,
                "available_capacity": total_shelter_capacity - current_shelter_occupancy
            },
            "hospitals": {
                "total": total_hospitals,
                "total_beds": total_hospital_beds,
                "available_beds": available_hospital_beds,
                "utilization_rate": round((total_hospital_beds - available_hospital_beds) / total_hospital_beds * 100, 2) if total_hospital_beds > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching resource overview: {str(e)}")
