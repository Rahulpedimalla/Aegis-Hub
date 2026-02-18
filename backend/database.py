from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables (optional)
try:
    load_dotenv()
except:
    pass

# Database connection - Using SQLite instead of PostgreSQL.
# Pin default SQLite path to backend directory so cwd does not change DB target.
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "disaster_response.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Organization Model
class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    type = Column(String, nullable=False)  # Government, NGO, Volunteer Group, Private
    category = Column(String, nullable=False)  # Emergency Response, Medical, Relief, Logistics
    address = Column(String)
    contact_person = Column(String)
    contact_phone = Column(String)
    contact_email = Column(String)
    capacity = Column(Integer, default=0)  # Number of people they can handle
    current_load = Column(Integer, default=0)  # Current number of people being helped
    status = Column(String, default="Active")  # Active, Inactive, Overloaded
    created_at = Column(DateTime, default=datetime.utcnow)

# Division Model
class Division(Base):
    __tablename__ = "divisions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"))
    type = Column(String, nullable=False)  # Medical, Rescue, Logistics, Communication
    description = Column(Text)
    capacity = Column(Integer, default=0)
    current_load = Column(Integer, default=0)
    status = Column(String, default="Active")
    created_at = Column(DateTime, default=datetime.utcnow)

# Staff Model
class Staff(Base):
    __tablename__ = "staff"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"))
    division_id = Column(String, ForeignKey("divisions.id"), nullable=True)
    role = Column(String, nullable=False)  # Manager, Worker, Specialist, Volunteer
    skills = Column(Text)  # JSON string of skills
    contact_phone = Column(String)
    contact_email = Column(String)
    availability = Column(String, default="Available")  # Available, Busy, Off-duty
    current_location = Column(String)
    status = Column(String, default="Active")
    created_at = Column(DateTime, default=datetime.utcnow)

# SOS Request Model (Enhanced)
class SOSRequest(Base):
    __tablename__ = "sos_requests"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id = Column(String, unique=True, index=True)  # n8n ID
    status = Column(String, default="Pending")  # Pending, In Progress, Done, Cancelled
    people = Column(Integer, default=1)
    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    text = Column(Text)
    place = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    category = Column(String)  # Needs Rescue, Medical, Food, etc.
    priority = Column(Integer, default=1)  # 1-5, 5 being highest
    assigned_to = Column(String, ForeignKey("staff.id"), nullable=True)
    assigned_organization = Column(String, ForeignKey("organizations.id"), nullable=True)
    assigned_division = Column(String, ForeignKey("divisions.id"), nullable=True)
    notes = Column(Text, nullable=True)
    estimated_completion = Column(DateTime, nullable=True)
    actual_completion = Column(DateTime, nullable=True)
    assignment_time = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Ticket Update History Model
class TicketUpdate(Base):
    __tablename__ = "ticket_updates"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(String, ForeignKey("sos_requests.id"))
    updated_by = Column(String, ForeignKey("staff.id"))
    field_name = Column(String, nullable=False)  # status, assigned_to, notes, etc.
    old_value = Column(Text)
    new_value = Column(Text)
    update_time = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

# Shelter Model (Enhanced)
class Shelter(Base):
    __tablename__ = "shelters"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    address = Column(String)
    capacity = Column(Integer, default=0)
    current_occupancy = Column(Integer, default=0)
    type = Column(String)  # Emergency, Temporary, Permanent
    status = Column(String, default="Active")  # Active, Inactive, Full
    contact_person = Column(String)
    contact_phone = Column(String)
    facilities = Column(Text)  # JSON string of available facilities
    created_at = Column(DateTime, default=datetime.utcnow)

# Hospital Model (Enhanced)
class Hospital(Base):
    __tablename__ = "hospitals"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    address = Column(String)
    total_beds = Column(Integer, default=0)
    available_beds = Column(Integer, default=0)
    icu_beds = Column(Integer, default=0)
    available_icu = Column(Integer, default=0)
    contact_phone = Column(String)
    specialties = Column(Text)  # JSON string of medical specialties
    emergency_services = Column(Text)  # JSON string of emergency services
    created_at = Column(DateTime, default=datetime.utcnow)

# Resource Center Model (Enhanced)
class ResourceCenter(Base):
    __tablename__ = "resource_centers"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    address = Column(String)
    type = Column(String)  # Food, Medicine, Clothing, etc.
    inventory = Column(Text)  # JSON string of available items
    contact_person = Column(String)
    contact_phone = Column(String)
    capacity = Column(Integer, default=0)
    current_stock = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

# User Model for Authentication (Enhanced)
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="viewer")  # admin, responder, viewer
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    division_id = Column(String, ForeignKey("divisions.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
