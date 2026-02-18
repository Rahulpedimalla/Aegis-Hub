from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import math

from database import get_db, Shelter, Organization
from models import ShelterCreate, ShelterUpdate, ShelterResponse
from routes.auth_routes import require_roles

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

@router.get("/", response_model=List[ShelterResponse])
async def get_shelters(
    available_only: bool = Query(False, description="Show only shelters with available capacity"),
    db: Session = Depends(get_db)
):
    """Get all shelters with optional filtering"""
    query = db.query(Shelter)
    
    if available_only:
        query = query.filter(Shelter.current_occupancy < Shelter.capacity)
    
    shelters = query.all()
    return shelters

@router.get("/nearby")
async def get_nearby_shelters(
    latitude: float = Query(..., description="Current latitude"),
    longitude: float = Query(..., description="Current longitude"),
    radius_km: float = Query(50, description="Search radius in kilometers"),
    min_capacity: int = Query(0, description="Minimum available capacity"),
    db: Session = Depends(get_db)
):
    """Find nearby shelters with available capacity"""
    shelters = db.query(Shelter).filter(
        Shelter.current_occupancy < Shelter.capacity
    ).all()
    
    nearby_shelters = []
    for shelter in shelters:
        distance = calculate_distance(latitude, longitude, shelter.latitude, shelter.longitude)
        available_capacity = shelter.capacity - shelter.current_occupancy
        
        if distance <= radius_km and available_capacity >= min_capacity:
            nearby_shelters.append({
                "id": str(shelter.id),
                "name": shelter.name,
                "address": shelter.address,
                "latitude": shelter.latitude,
                "longitude": shelter.longitude,
                "distance_km": round(distance, 2),
                "available_capacity": available_capacity,
                "total_capacity": shelter.capacity,
                "current_occupancy": shelter.current_occupancy,
                "status": shelter.status,
                "facilities": shelter.facilities,
                "contact_person": shelter.contact_person,
                "contact_phone": shelter.contact_phone
            })
    
    # Sort by distance
    nearby_shelters.sort(key=lambda x: x["distance_km"])
    return nearby_shelters

@router.get("/emergency")
async def get_emergency_shelters(
    people_count: int = Query(..., description="Number of people needing shelter"),
    latitude: float = Query(..., description="Current latitude"),
    longitude: float = Query(..., description="Current longitude"),
    db: Session = Depends(get_db)
):
    """Find emergency shelters that can accommodate the specified number of people"""
    shelters = db.query(Shelter).filter(
        Shelter.status == "Active",
        (Shelter.capacity - Shelter.current_occupancy) >= people_count
    ).all()
    
    emergency_shelters = []
    for shelter in shelters:
        distance = calculate_distance(latitude, longitude, shelter.latitude, shelter.longitude)
        available_capacity = shelter.capacity - shelter.current_occupancy
        
        emergency_shelters.append({
            "id": str(shelter.id),
            "name": shelter.name,
            "address": shelter.address,
            "latitude": shelter.latitude,
            "longitude": shelter.longitude,
            "distance_km": round(distance, 2),
            "available_capacity": available_capacity,
            "can_accommodate": available_capacity >= people_count,
            "facilities": shelter.facilities,
            "contact_person": shelter.contact_person,
            "contact_phone": shelter.contact_phone,
            "estimated_travel_time": round(distance * 2, 1)  # Rough estimate: 2 min per km
        })
    
    # Sort by distance and capacity
    emergency_shelters.sort(key=lambda x: (x["distance_km"], -x["available_capacity"]))
    return emergency_shelters

@router.get("/stats")
async def get_shelter_stats(db: Session = Depends(get_db)):
    """Get comprehensive shelter statistics"""
    total_shelters = db.query(func.count(Shelter.id)).scalar()
    active_shelters = db.query(func.count(Shelter.id)).filter(Shelter.status == "Active").scalar()
    total_capacity = db.query(func.sum(Shelter.capacity)).scalar() or 0
    current_occupancy = db.query(func.sum(Shelter.current_occupancy)).scalar() or 0
    available_capacity = total_capacity - current_occupancy
    utilization_rate = round((current_occupancy / total_capacity * 100), 2) if total_capacity > 0 else 0
    
    # Shelters by capacity utilization
    full_shelters = db.query(func.count(Shelter.id)).filter(
        Shelter.current_occupancy >= Shelter.capacity * 0.9
    ).scalar()
    
    medium_shelters = db.query(func.count(Shelter.id)).filter(
        Shelter.current_occupancy >= Shelter.capacity * 0.5,
        Shelter.current_occupancy < Shelter.capacity * 0.9
    ).scalar()
    
    empty_shelters = db.query(func.count(Shelter.id)).filter(
        Shelter.current_occupancy < Shelter.capacity * 0.5
    ).scalar()
    
    return {
        "total_shelters": total_shelters,
        "active_shelters": active_shelters,
        "total_capacity": total_capacity,
        "current_occupancy": current_occupancy,
        "available_capacity": available_capacity,
        "utilization_rate": utilization_rate,
        "capacity_distribution": {
            "full": full_shelters,
            "medium": medium_shelters,
            "empty": empty_shelters
        }
    }

@router.get("/{shelter_id}", response_model=ShelterResponse)
async def get_shelter(shelter_id: str, db: Session = Depends(get_db)):
    """Get a specific shelter by ID"""
    shelter = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not shelter:
        raise HTTPException(status_code=404, detail="Shelter not found")
    return shelter

@router.post("/", response_model=ShelterResponse)
async def create_shelter(
    shelter_data: ShelterCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Create a new shelter"""
    try:
        db_shelter = Shelter(**shelter_data.dict())
        db.add(db_shelter)
        db.commit()
        db.refresh(db_shelter)
        return db_shelter
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating shelter: {str(e)}")

@router.put("/{shelter_id}", response_model=ShelterResponse)
async def update_shelter(
    shelter_id: str,
    shelter_update: ShelterUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Update shelter information"""
    shelter = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not shelter:
        raise HTTPException(status_code=404, detail="Shelter not found")
    
    update_data = shelter_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(shelter, field, value)
    
    db.commit()
    db.refresh(shelter)
    return shelter

@router.delete("/{shelter_id}")
async def delete_shelter(
    shelter_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin")),
):
    """Delete a shelter"""
    shelter = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not shelter:
        raise HTTPException(status_code=404, detail="Shelter not found")
    
    db.delete(shelter)
    db.commit()
    return {"message": "Shelter deleted successfully"}

@router.post("/{shelter_id}/check-in")
async def check_in_people(
    shelter_id: str,
    people_count: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Check in people to a shelter"""
    shelter = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not shelter:
        raise HTTPException(status_code=404, detail="Shelter not found")
    
    if shelter.current_occupancy + people_count > shelter.capacity:
        raise HTTPException(
            status_code=400, 
            detail=f"Shelter capacity exceeded. Available: {shelter.capacity - shelter.current_occupancy}"
        )
    
    shelter.current_occupancy += people_count
    db.commit()
    db.refresh(shelter)
    
    return {
        "message": f"{people_count} people checked in successfully",
        "current_occupancy": shelter.current_occupancy,
        "available_capacity": shelter.capacity - shelter.current_occupancy
    }

@router.post("/{shelter_id}/check-out")
async def check_out_people(
    shelter_id: str,
    people_count: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Check out people from a shelter"""
    shelter = db.query(Shelter).filter(Shelter.id == shelter_id).first()
    if not shelter:
        raise HTTPException(status_code=404, detail="Shelter not found")
    
    if shelter.current_occupancy - people_count < 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot check out more people than currently in shelter"
        )
    
    shelter.current_occupancy -= people_count
    db.commit()
    db.refresh(shelter)
    
    return {
        "message": f"{people_count} people checked out successfully",
        "current_occupancy": shelter.current_occupancy,
        "available_capacity": shelter.capacity - shelter.current_occupancy
    }
