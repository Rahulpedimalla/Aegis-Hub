from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
# Removed geoalchemy2 import for SQLite compatibility

from database import get_db, Hospital
from models import HospitalCreate, HospitalUpdate, HospitalResponse
from routes.auth_routes import require_roles
import uuid
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=HospitalResponse)
async def create_hospital(
    hospital_data: HospitalCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Create a new hospital"""
    try:
        db_hospital = Hospital(
            name=hospital_data.name,
            longitude=hospital_data.longitude,
            latitude=hospital_data.latitude,
            address=hospital_data.address,
            total_beds=hospital_data.total_beds,
            available_beds=hospital_data.total_beds,  # Initially all beds are available
            icu_beds=hospital_data.icu_beds,
            available_icu=hospital_data.icu_beds,  # Initially all ICU beds are available
            contact_phone=hospital_data.contact_phone
        )
        
        db.add(db_hospital)
        db.commit()
        db.refresh(db_hospital)
        
        return db_hospital
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating hospital: {str(e)}")

@router.get("/", response_model=List[HospitalResponse])
async def get_hospitals(
    region: Optional[str] = Query(None, description="Filter by region"),
    has_beds: Optional[bool] = Query(None, description="Filter by bed availability"),
    db: Session = Depends(get_db)
):
    """Get hospitals with filtering options"""
    query = db.query(Hospital)
    
    if has_beds is not None:
        if has_beds:
            query = query.filter(Hospital.available_beds > 0)
        else:
            query = query.filter(Hospital.available_beds == 0)
    
    # Region filtering
    if region:
        if region.lower() == "south":
            query = query.filter(Hospital.longitude >= 77.0, Hospital.longitude <= 78.4)
        elif region.lower() == "central":
            query = query.filter(Hospital.longitude >= 78.4, Hospital.longitude <= 79.6)
        elif region.lower() == "north":
            query = query.filter(Hospital.longitude >= 79.6, Hospital.longitude <= 81.0)
    
    return query.all()

@router.get("/nearby")
async def get_nearby_hospitals(
    latitude: float = Query(..., description="Current latitude"),
    longitude: float = Query(..., description="Current longitude"),
    radius_km: float = Query(10.0, description="Search radius in kilometers"),
    limit: int = Query(10, le=50, description="Maximum number of hospitals to return"),
    db: Session = Depends(get_db)
):
    """Get hospitals within a specified radius"""
    try:
        # Convert km to degrees (approximate)
        radius_degrees = radius_km / 111.0
        
        hospitals = db.query(Hospital).filter(
            Hospital.longitude >= longitude - radius_degrees,
            Hospital.longitude <= longitude + radius_degrees,
            Hospital.latitude >= latitude - radius_degrees,
            Hospital.latitude <= latitude + radius_degrees
        ).limit(limit).all()
        
        # Calculate distances and sort
        hospital_distances = []
        for hospital in hospitals:
            # Simple distance calculation (can be improved with PostGIS functions)
            lat_diff = abs(hospital.latitude - latitude)
            lon_diff = abs(hospital.longitude - longitude)
            distance = ((lat_diff ** 2 + lon_diff ** 2) ** 0.5) * 111.0  # Convert to km
            
            hospital_distances.append({
                "id": str(hospital.id),
                "name": hospital.name,
                "longitude": hospital.longitude,
                "latitude": hospital.latitude,
                "address": hospital.address,
                "total_beds": hospital.total_beds,
                "available_beds": hospital.available_beds,
                "icu_beds": hospital.icu_beds,
                "available_icu": hospital.available_icu,
                "contact_phone": hospital.contact_phone,
                "distance_km": round(distance, 2)
            })
        
        # Sort by distance
        hospital_distances.sort(key=lambda x: x["distance_km"])
        
        return hospital_distances[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding nearby hospitals: {str(e)}")

@router.get("/{hospital_id}", response_model=HospitalResponse)
async def get_hospital(hospital_id: str, db: Session = Depends(get_db)):
    """Get a specific hospital by ID"""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    return hospital

@router.put("/{hospital_id}", response_model=HospitalResponse)
async def update_hospital(
    hospital_id: str,
    hospital_update: HospitalUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Update hospital information"""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    update_data = hospital_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(hospital, field, value)
    
    db.commit()
    db.refresh(hospital)
    
    return hospital

@router.delete("/{hospital_id}")
async def delete_hospital(
    hospital_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin")),
):
    """Delete a hospital (admin only)"""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    db.delete(hospital)
    db.commit()
    
    return {"message": "Hospital deleted successfully"}

@router.get("/overview/stats")
async def get_hospital_overview(db: Session = Depends(get_db)):
    """Get hospital overview statistics"""
    try:
        total_hospitals = db.query(func.count(Hospital.id)).scalar()
        total_beds = db.query(func.sum(Hospital.total_beds)).scalar() or 0
        available_beds = db.query(func.sum(Hospital.available_beds)).scalar() or 0
        total_icu_beds = db.query(func.sum(Hospital.icu_beds)).scalar() or 0
        available_icu_beds = db.query(func.sum(Hospital.available_icu)).scalar() or 0
        
        # Region breakdown
        regions = [
            ("South Telangana", 77.0, 78.4),
            ("Central Telangana", 78.4, 79.6),
            ("North Telangana", 79.6, 81.0)
        ]
        
        region_stats = []
        for region_name, west_lon, east_lon in regions:
            region_hospitals = db.query(Hospital).filter(
                Hospital.longitude >= west_lon,
                Hospital.longitude <= east_lon
            ).all()
            
            region_total_beds = sum(h.total_beds for h in region_hospitals)
            region_available_beds = sum(h.available_beds for h in region_hospitals)
            region_total_icu = sum(h.icu_beds for h in region_hospitals)
            region_available_icu = sum(h.available_icu for h in region_hospitals)
            
            region_stats.append({
                "region": region_name,
                "hospitals": len(region_hospitals),
                "total_beds": region_total_beds,
                "available_beds": region_available_beds,
                "total_icu": region_total_icu,
                "available_icu": region_available_icu,
                "utilization_rate": round((region_total_beds - region_available_beds) / region_total_beds * 100, 2) if region_total_beds > 0 else 0
            })
        
        return {
            "total_hospitals": total_hospitals,
            "total_beds": total_beds,
            "available_beds": available_beds,
            "total_icu_beds": total_icu_beds,
            "available_icu_beds": available_icu_beds,
            "overall_utilization_rate": round((total_beds - available_beds) / total_beds * 100, 2) if total_beds > 0 else 0,
            "region_breakdown": region_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching hospital overview: {str(e)}")
