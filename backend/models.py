from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# Organization Models
class OrganizationBase(BaseModel):
    name: str = Field(..., description="Organization name")
    type: str = Field(..., description="Type: Government, NGO, Volunteer Group, Private")
    category: str = Field(..., description="Category: Emergency Response, Medical, Relief, Logistics")
    address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    capacity: int = Field(0, ge=0, description="Number of people they can handle")

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=0)
    current_load: Optional[int] = None
    status: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

class OrganizationResponse(OrganizationBase):
    id: str
    current_load: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Division Models
class DivisionBase(BaseModel):
    name: str = Field(..., description="Division name")
    organization_id: str = Field(..., description="Parent organization ID")
    type: str = Field(..., description="Type: Medical, Rescue, Logistics, Communication")
    description: Optional[str] = None
    capacity: int = Field(0, ge=0)

class DivisionCreate(DivisionBase):
    pass

class DivisionUpdate(BaseModel):
    name: Optional[str] = None
    organization_id: Optional[str] = None
    type: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=0)
    current_load: Optional[int] = None
    status: Optional[str] = None
    description: Optional[str] = None

class DivisionResponse(DivisionBase):
    id: str
    current_load: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Staff Models
class StaffBase(BaseModel):
    name: str = Field(..., description="Staff member name")
    organization_id: str = Field(..., description="Organization ID")
    division_id: Optional[str] = None
    role: str = Field(..., description="Role: Manager, Worker, Specialist, Volunteer")
    skills: Optional[str] = None  # JSON string of skills
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    current_location: Optional[str] = None

class StaffCreate(StaffBase):
    pass

class StaffUpdate(BaseModel):
    name: Optional[str] = None
    organization_id: Optional[str] = None
    division_id: Optional[str] = None
    role: Optional[str] = None
    skills: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    availability: Optional[str] = None
    current_location: Optional[str] = None
    status: Optional[str] = None

class StaffResponse(StaffBase):
    id: str
    availability: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# SOS Request Models (Enhanced)
class SOSRequestBase(BaseModel):
    people: int = Field(..., ge=1, description="Number of people affected")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    text: str = Field(..., description="Description of the emergency")
    place: str = Field(..., description="Location name")
    category: str = Field(..., description="Type of emergency")

class SOSRequestCreate(SOSRequestBase):
    external_id: str = Field(..., description="External ID from n8n")

class SOSIntakeRequest(BaseModel):
    external_id: Optional[str] = None
    text: Optional[str] = None
    voice_transcript: Optional[str] = None
    people: Optional[int] = Field(1, ge=1)
    longitude: float = Field(..., ge=-180, le=180)
    latitude: float = Field(..., ge=-90, le=90)
    place: Optional[str] = None
    category_hint: Optional[str] = None
    source: str = "mobile_app"
    contact_phone: Optional[str] = None

class SOSRequestUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    assigned_to: Optional[str] = None
    assigned_organization: Optional[str] = None
    assigned_division: Optional[str] = None
    notes: Optional[str] = None
    estimated_completion: Optional[datetime] = None

class SOSRequestResponse(SOSRequestBase):
    id: str
    external_id: str
    status: str
    priority: int
    assigned_to: Optional[str]
    assigned_organization: Optional[str]
    assigned_division: Optional[str]
    notes: Optional[str]
    timestamp: datetime
    estimated_completion: Optional[datetime]
    actual_completion: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Ticket Update History Models
class TicketUpdateBase(BaseModel):
    ticket_id: str
    updated_by: str
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    notes: Optional[str] = None

class TicketUpdateCreate(TicketUpdateBase):
    pass

class TicketUpdateResponse(TicketUpdateBase):
    id: str
    update_time: datetime

    class Config:
        from_attributes = True

# Shelter Models (Enhanced)
class ShelterBase(BaseModel):
    name: str
    longitude: float
    latitude: float
    address: str
    capacity: int
    type: str
    contact_person: str
    contact_phone: str
    organization_id: Optional[str] = None
    facilities: Optional[str] = None  # JSON string of facilities

class ShelterCreate(ShelterBase):
    pass

class ShelterUpdate(BaseModel):
    current_occupancy: Optional[int] = None
    status: Optional[str] = None
    facilities: Optional[str] = None

class ShelterResponse(ShelterBase):
    id: str
    current_occupancy: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Hospital Models (Enhanced)
class HospitalBase(BaseModel):
    name: str
    longitude: float
    latitude: float
    address: str
    total_beds: int
    icu_beds: int
    contact_phone: str
    organization_id: Optional[str] = None
    specialties: Optional[str] = None  # JSON string of specialties
    emergency_services: Optional[str] = None  # JSON string of emergency services

class HospitalCreate(HospitalBase):
    pass

class HospitalUpdate(BaseModel):
    available_beds: Optional[int] = None
    available_icu: Optional[int] = None
    specialties: Optional[str] = None
    emergency_services: Optional[str] = None

class HospitalResponse(HospitalBase):
    id: str
    available_beds: int
    available_icu: int
    created_at: datetime

    class Config:
        from_attributes = True

# Resource Center Models (Enhanced)
class ResourceCenterBase(BaseModel):
    name: str
    longitude: float
    latitude: float
    address: str
    type: str
    inventory: str
    contact_person: str
    contact_phone: str
    organization_id: Optional[str] = None
    capacity: int = Field(0, ge=0)
    current_stock: int = Field(0, ge=0)

class ResourceCenterCreate(ResourceCenterBase):
    pass

class ResourceCenterUpdate(BaseModel):
    inventory: Optional[str] = None
    current_stock: Optional[int] = Field(None, ge=0)
    capacity: Optional[int] = Field(None, ge=0)
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None

class ResourceCenterResponse(ResourceCenterBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

# Dashboard Models (Enhanced)
class DashboardStats(BaseModel):
    total_sos: int
    pending_sos: int
    in_progress_sos: int
    completed_sos: int
    total_people_affected: int
    total_shelter_capacity: int
    available_shelter_capacity: int
    total_hospital_beds: int
    available_hospital_beds: int
    total_organizations: int
    total_staff: int
    active_staff: int

class OrganizationDashboardStats(BaseModel):
    organization_id: str
    organization_name: str
    total_staff: int
    active_staff: int
    total_divisions: int
    active_divisions: int
    assigned_tickets: int
    completed_tickets: int
    current_load: int
    capacity: int

class RegionStats(BaseModel):
    region: str
    sos_count: int
    people_affected: int
    shelter_capacity: int
    shelter_available: int

# Authentication Models (Enhanced)
class UserLogin(BaseModel):
    username: str
    password: str
    role: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "viewer"
    organization_id: Optional[str] = None
    division_id: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    organization_id: Optional[str]
    division_id: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

# Map and Location Models
class Location(BaseModel):
    longitude: float
    latitude: float
    address: str

class MapBounds(BaseModel):
    north: float
    south: float
    east: float
    west: float

class SOSMapData(BaseModel):
    id: str
    longitude: float
    latitude: float
    status: str
    category: str
    priority: int
    people: int
    place: str

    class Config:
        from_attributes = True

# Flood Detection Models
class FloodArea(BaseModel):
    id: str
    name: str
    coordinates: List[List[float]]  # [[lng, lat], [lng, lat], ...]
    severity: str  # High, Medium, Low
    affected_area_km2: float
    affected_population: int
    confidence: float
    detection_method: str
    threshold_used: float
    analysis_date: str

class FloodAnalysisRequest(BaseModel):
    pre_flood_start: str
    pre_flood_end: str
    post_flood_start: str
    post_flood_end: str
    threshold: float = -5.0
    region: str = "Telangana"
    analysis_type: str = "Sentinel-1 VH Change Detection"

class FloodAnalysisResponse(BaseModel):
    flood_areas: List[FloodArea]
    analysis_parameters: FloodAnalysisRequest
    total_affected_area_km2: float
    total_affected_population: int
    average_confidence: float
    analysis_completed_at: str
    data_source: str
    processing_time_seconds: float
