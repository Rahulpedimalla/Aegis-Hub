from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import math

from database import get_db, ResourceCenter, Organization
from models import ResourceCenterCreate, ResourceCenterUpdate, ResourceCenterResponse
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

@router.get("/", response_model=List[ResourceCenterResponse])
async def get_resource_centers(
    type: Optional[str] = Query(None, description="Filter by resource type"),
    available_only: bool = Query(False, description="Show only centers with available stock"),
    db: Session = Depends(get_db)
):
    """Get all resource centers with optional filtering"""
    query = db.query(ResourceCenter)
    
    if type:
        query = query.filter(ResourceCenter.type.ilike(f"%{type}%"))
    
    if available_only:
        query = query.filter(ResourceCenter.current_stock > 0)
    
    resource_centers = query.all()
    return resource_centers

@router.get("/emergency-supplies")
async def get_emergency_supplies(
    latitude: float = Query(..., description="Current latitude"),
    longitude: float = Query(..., description="Current longitude"),
    radius_km: float = Query(100, description="Search radius in kilometers"),
    db: Session = Depends(get_db)
):
    """Find emergency supplies near a location"""
    # Define emergency supply types
    emergency_types = [
        "Life Jackets", "First Aid Kits", "Emergency Food", "Water", 
        "Blankets", "Medical Supplies", "Rescue Equipment", "Communication Devices"
    ]
    
    emergency_centers = []
    
    for supply_type in emergency_types:
        centers = db.query(ResourceCenter).filter(
            ResourceCenter.type.ilike(f"%{supply_type}%"),
            ResourceCenter.current_stock > 0
        ).all()
        
        for center in centers:
            distance = calculate_distance(latitude, longitude, center.latitude, center.longitude)
            
            if distance <= radius_km:
                emergency_centers.append({
                    "id": str(center.id),
                    "name": center.name,
                    "type": center.type,
                    "latitude": center.latitude,
                    "longitude": center.longitude,
                    "distance_km": round(distance, 2),
                    "available_stock": center.current_stock,
                    "total_capacity": center.capacity,
                    "inventory": center.inventory,
                    "contact_person": center.contact_person,
                    "contact_phone": center.contact_phone,
                    "address": center.address,
                    "estimated_travel_time": round(distance * 2, 1)  # 2 min per km
                })
    
    # Sort by distance
    emergency_centers.sort(key=lambda x: x["distance_km"])
    return emergency_centers

@router.get("/life-jackets")
async def get_life_jackets(
    latitude: float = Query(..., description="Current latitude"),
    longitude: float = Query(..., description="Current longitude"),
    quantity_needed: int = Query(..., description="Number of life jackets needed"),
    radius_km: float = Query(100, description="Search radius in kilometers"),
    db: Session = Depends(get_db)
):
    """Find life jackets near a location"""
    centers = db.query(ResourceCenter).filter(
        ResourceCenter.type.ilike("%life jacket%"),
        ResourceCenter.current_stock >= quantity_needed
    ).all()
    
    available_centers = []
    for center in centers:
        distance = calculate_distance(latitude, longitude, center.latitude, center.longitude)
        
        if distance <= radius_km:
            available_centers.append({
                "id": str(center.id),
                "name": center.name,
                "latitude": center.latitude,
                "longitude": center.longitude,
                "distance_km": round(distance, 2),
                "available_stock": center.current_stock,
                "can_provide": center.current_stock >= quantity_needed,
                "contact_person": center.contact_person,
                "contact_phone": center.contact_phone,
                "address": center.address,
                "estimated_travel_time": round(distance * 2, 1)
            })
    
    # Sort by distance
    available_centers.sort(key=lambda x: x["distance_km"])
    return available_centers

@router.get("/first-aid-kits")
async def get_first_aid_kits(
    latitude: float = Query(..., description="Current latitude"),
    longitude: float = Query(..., description="Current longitude"),
    quantity_needed: int = Query(..., description="Number of first aid kits needed"),
    radius_km: float = Query(100, description="Search radius in kilometers"),
    db: Session = Depends(get_db)
):
    """Find first aid kits near a location"""
    centers = db.query(ResourceCenter).filter(
        ResourceCenter.type.ilike("%first aid%"),
        ResourceCenter.current_stock >= quantity_needed
    ).all()
    
    available_centers = []
    for center in centers:
        distance = calculate_distance(latitude, longitude, center.latitude, center.longitude)
        
        if distance <= radius_km:
            available_centers.append({
                "id": str(center.id),
                "name": center.name,
                "latitude": center.latitude,
                "longitude": center.longitude,
                "distance_km": round(distance, 2),
                "available_stock": center.current_stock,
                "can_provide": center.current_stock >= quantity_needed,
                "contact_person": center.contact_person,
                "contact_phone": center.contact_phone,
                "address": center.address,
                "estimated_travel_time": round(distance * 2, 1)
            })
    
    # Sort by distance
    available_centers.sort(key=lambda x: x["distance_km"])
    return available_centers

@router.get("/nearby")
async def get_nearby_resource_centers(
    latitude: float = Query(..., description="Current latitude"),
    longitude: float = Query(..., description="Current longitude"),
    radius_km: float = Query(50, description="Search radius in kilometers"),
    min_stock: int = Query(0, description="Minimum available stock"),
    db: Session = Depends(get_db)
):
    """Find nearby resource centers with available stock"""
    centers = db.query(ResourceCenter).filter(
        ResourceCenter.current_stock >= min_stock
    ).all()
    
    nearby_centers = []
    for center in centers:
        distance = calculate_distance(latitude, longitude, center.latitude, center.longitude)
        
        if distance <= radius_km:
            nearby_centers.append({
                "id": str(center.id),
                "name": center.name,
                "type": center.type,
                "latitude": center.latitude,
                "longitude": center.longitude,
                "distance_km": round(distance, 2),
                "available_stock": center.current_stock,
                "total_capacity": center.capacity,
                "inventory": center.inventory,
                "contact_person": center.contact_person,
                "contact_phone": center.contact_phone,
                "address": center.address
            })
    
    # Sort by distance
    nearby_centers.sort(key=lambda x: x["distance_km"])
    return nearby_centers

@router.get("/stats")
async def get_resource_stats(db: Session = Depends(get_db)):
    """Get comprehensive resource statistics"""
    total_centers = db.query(func.count(ResourceCenter.id)).scalar()
    total_capacity = db.query(func.sum(ResourceCenter.capacity)).scalar() or 0
    current_stock = db.query(func.sum(ResourceCenter.current_stock)).scalar() or 0
    available_stock = current_stock
    utilization_rate = round((current_stock / total_capacity * 100), 2) if total_capacity > 0 else 0
    
    # Resource types breakdown
    type_stats = db.query(
        ResourceCenter.type,
        func.count(ResourceCenter.id).label('count'),
        func.sum(ResourceCenter.capacity).label('total_capacity'),
        func.sum(ResourceCenter.current_stock).label('total_stock')
    ).group_by(ResourceCenter.type).all()
    
    # Low stock centers (less than 20% capacity)
    low_stock_centers = db.query(func.count(ResourceCenter.id)).filter(
        ResourceCenter.current_stock < ResourceCenter.capacity * 0.2
    ).scalar()
    
    # Out of stock centers
    out_of_stock_centers = db.query(func.count(ResourceCenter.id)).filter(
        ResourceCenter.current_stock == 0
    ).scalar()
    
    return {
        "total_centers": total_centers,
        "total_capacity": total_capacity,
        "current_stock": current_stock,
        "available_stock": available_stock,
        "utilization_rate": utilization_rate,
        "low_stock_centers": low_stock_centers,
        "out_of_stock_centers": out_of_stock_centers,
        "type_breakdown": [
            {
                "type": item.type,
                "count": item.count,
                "total_capacity": item.total_capacity or 0,
                "total_stock": item.total_stock or 0
            }
            for item in type_stats
        ]
    }

@router.get("/{center_id}", response_model=ResourceCenterResponse)
async def get_resource_center(center_id: str, db: Session = Depends(get_db)):
    """Get a specific resource center by ID"""
    center = db.query(ResourceCenter).filter(ResourceCenter.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Resource center not found")
    return center

@router.post("/", response_model=ResourceCenterResponse)
async def create_resource_center(
    resource_data: ResourceCenterCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Create a new resource center"""
    try:
        db_center = ResourceCenter(**resource_data.dict())
        db.add(db_center)
        db.commit()
        db.refresh(db_center)
        return db_center
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating resource center: {str(e)}")

@router.put("/{center_id}", response_model=ResourceCenterResponse)
async def update_resource_center(
    center_id: str,
    resource_update: ResourceCenterUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Update resource center information"""
    center = db.query(ResourceCenter).filter(ResourceCenter.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Resource center not found")
    
    update_data = resource_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(center, field, value)
    
    db.commit()
    db.refresh(center)
    return center

@router.delete("/{center_id}")
async def delete_resource_center(
    center_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin")),
):
    """Delete a resource center"""
    center = db.query(ResourceCenter).filter(ResourceCenter.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Resource center not found")
    
    db.delete(center)
    db.commit()
    return {"message": "Resource center deleted successfully"}

@router.post("/{center_id}/allocate")
async def allocate_resources(
    center_id: str,
    allocation_data: dict,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Allocate resources from a center"""
    center = db.query(ResourceCenter).filter(ResourceCenter.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Resource center not found")
    
    quantity = allocation_data.get('quantity', 0)
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    
    if center.current_stock < quantity:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient stock. Available: {center.current_stock}"
        )
    
    center.current_stock -= quantity
    db.commit()
    db.refresh(center)
    
    return {
        "message": f"{quantity} units allocated successfully",
        "remaining_stock": center.current_stock,
        "total_capacity": center.capacity
    }

@router.post("/{center_id}/restock")
async def restock_resources(
    center_id: str,
    restock_data: dict,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin", "responder")),
):
    """Restock resources at a center"""
    center = db.query(ResourceCenter).filter(ResourceCenter.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Resource center not found")
    
    quantity = restock_data.get('quantity', 0)
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    
    if center.current_stock + quantity > center.capacity:
        raise HTTPException(
            status_code=400, 
            detail=f"Restock would exceed capacity. Available space: {center.capacity - center.current_stock}"
        )
    
    center.current_stock += quantity
    db.commit()
    db.refresh(center)
    
    return {
        "message": f"{quantity} units restocked successfully",
        "current_stock": center.current_stock,
        "total_capacity": center.capacity
    }
