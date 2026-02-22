#!/usr/bin/env python3
"""
Idempotent database initializer for AegisHub Telangana deployment.
"""

import os
import re
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from passlib.context import CryptContext

from database import (
    Base,
    Division,
    Hospital,
    Organization,
    ResourceCenter,
    SOSRequest,
    SessionLocal,
    Shelter,
    Staff,
    User,
    engine,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def upsert_by_name(db, model, payload):
    record = db.query(model).filter(model.name == payload["name"]).first()
    if record:
        for k, v in payload.items():
            setattr(record, k, v)
        return record
    record = model(**payload)
    db.add(record)
    db.flush()
    return record


def upsert_user(db, payload):
    user = db.query(User).filter(User.username == payload["username"]).first()
    if user:
        for k, v in payload.items():
            setattr(user, k, v)
        return user
    user = User(**payload)
    db.add(user)
    db.flush()
    return user


def upsert_division(db, payload):
    row = (
        db.query(Division)
        .filter(Division.name == payload["name"], Division.organization_id == payload["organization_id"])
        .first()
    )
    if row:
        for k, v in payload.items():
            setattr(row, k, v)
        return row
    row = Division(**payload)
    db.add(row)
    db.flush()
    return row


def upsert_staff(db, payload):
    row = (
        db.query(Staff)
        .filter(Staff.name == payload["name"], Staff.organization_id == payload["organization_id"])
        .first()
    )
    if row:
        for k, v in payload.items():
            setattr(row, k, v)
        return row
    row = Staff(**payload)
    db.add(row)
    db.flush()
    return row


def make_username(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", ".", (name or "").strip().lower())
    normalized = normalized.strip(".")
    return normalized or "responder"


def create_sample_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Organizations (Telangana-focused)
        organizations_data = [
            {
                "name": "Telangana State Disaster Management Authority",
                "type": "Government",
                "category": "Emergency Response",
                "address": "BRKR Bhavan, Tank Bund Road, Hyderabad, Telangana",
                "contact_person": "Dr. P. Venkata Ramana",
                "contact_phone": "+91-40-2324-0100",
                "contact_email": "controlroom@tsdma.telangana.gov.in",
                "capacity": 1800,
                "current_load": 0,
                "status": "Active",
            },
            {
                "name": "Telangana Fire and Emergency Services",
                "type": "Government",
                "category": "Rescue",
                "address": "Fire Services HQ, Lakdikapul, Hyderabad, Telangana",
                "contact_person": "M. Nagaraju",
                "contact_phone": "+91-40-2345-6789",
                "contact_email": "rescue@tgfire.gov.in",
                "capacity": 1200,
                "current_load": 0,
                "status": "Active",
            },
            {
                "name": "Greater Hyderabad Emergency Coordination Cell",
                "type": "Government",
                "category": "Logistics",
                "address": "GHMC Head Office, Tank Bund, Hyderabad, Telangana",
                "contact_person": "S. Manohar Reddy",
                "contact_phone": "+91-40-2111-1111",
                "contact_email": "operations@ghmc.gov.in",
                "capacity": 900,
                "current_load": 0,
                "status": "Active",
            },
            {
                "name": "Indian Red Cross Society Telangana",
                "type": "NGO",
                "category": "Relief",
                "address": "Himayatnagar, Hyderabad, Telangana",
                "contact_person": "A. Sirisha",
                "contact_phone": "+91-40-2475-4321",
                "contact_email": "response@redcross-telangana.org",
                "capacity": 700,
                "current_load": 0,
                "status": "Active",
            },
            {
                "name": "Telangana Medical Rapid Response Network",
                "type": "NGO",
                "category": "Medical",
                "address": "Secunderabad, Telangana",
                "contact_person": "Dr. R. Nishanth",
                "contact_phone": "+91-40-2999-8888",
                "contact_email": "medical@tmrrn.org",
                "capacity": 600,
                "current_load": 0,
                "status": "Active",
            },
        ]

        organizations = [upsert_by_name(db, Organization, payload) for payload in organizations_data]

        # Divisions
        divisions_data = [
            {
                "name": "Flood Rescue Unit",
                "organization_id": organizations[1].id,
                "type": "Rescue",
                "description": "Boat and swift-water rescue operations",
                "capacity": 250,
                "current_load": 0,
                "status": "Active",
            },
            {
                "name": "Medical Triage Unit",
                "organization_id": organizations[4].id,
                "type": "Medical",
                "description": "Emergency triage and trauma stabilization",
                "capacity": 220,
                "current_load": 0,
                "status": "Active",
            },
            {
                "name": "Shelter Logistics Unit",
                "organization_id": organizations[2].id,
                "type": "Logistics",
                "description": "Shelter setup, supplies and transport routing",
                "capacity": 180,
                "current_load": 0,
                "status": "Active",
            },
            {
                "name": "Communications and Control Unit",
                "organization_id": organizations[0].id,
                "type": "Communication",
                "description": "Command center coordination and public alerts",
                "capacity": 200,
                "current_load": 0,
                "status": "Active",
            },
            {
                "name": "Relief Field Support Unit",
                "organization_id": organizations[3].id,
                "type": "Logistics",
                "description": "On-ground relief coordination and distribution",
                "capacity": 160,
                "current_load": 0,
                "status": "Active",
            },
        ]

        divisions = [upsert_division(db, payload) for payload in divisions_data]

        # Staff
        staff_data = [
            {
                "name": "Harish Rao",
                "organization_id": organizations[1].id,
                "division_id": divisions[0].id,
                "role": "Manager",
                "skills": "fire response,smoke rescue,evacuation,incident command",
                "contact_phone": "+91-40-5000-1001",
                "contact_email": "harish.rao@tgfire.gov.in",
                "availability": "Available",
                "current_location": "Hyderabad",
                "status": "Active",
            },
            {
                "name": "Rakesh Yadav",
                "organization_id": organizations[1].id,
                "division_id": divisions[0].id,
                "role": "Specialist",
                "skills": "rescue,boat operations,swift water rescue,evacuation",
                "contact_phone": "+91-40-5000-1011",
                "contact_email": "rakesh.yadav@tgfire.gov.in",
                "availability": "Available",
                "current_location": "Warangal",
                "status": "Active",
            },
            {
                "name": "Naveen Chary",
                "organization_id": organizations[1].id,
                "division_id": divisions[0].id,
                "role": "Worker",
                "skills": "rescue,rope rescue,evacuation,field operations",
                "contact_phone": "+91-40-5000-1012",
                "contact_email": "naveen.chary@tgfire.gov.in",
                "availability": "Available",
                "current_location": "Nizamabad",
                "status": "Active",
            },
            {
                "name": "Shalini Das",
                "organization_id": organizations[1].id,
                "division_id": divisions[0].id,
                "role": "Worker",
                "skills": "rescue,community evacuation,emergency response,coordination",
                "contact_phone": "+91-40-5000-1013",
                "contact_email": "shalini.das@tgfire.gov.in",
                "availability": "Available",
                "current_location": "Hyderabad",
                "status": "Active",
            },
            {
                "name": "Dr. Sneha Reddy",
                "organization_id": organizations[4].id,
                "division_id": divisions[1].id,
                "role": "Specialist",
                "skills": "medical,trauma,first aid,triage",
                "contact_phone": "+91-40-5000-1002",
                "contact_email": "sneha.reddy@tmrrn.org",
                "availability": "Available",
                "current_location": "Secunderabad",
                "status": "Active",
            },
            {
                "name": "Dr. Aamir Khan",
                "organization_id": organizations[4].id,
                "division_id": divisions[1].id,
                "role": "Specialist",
                "skills": "medical,trauma,critical care,ambulance coordination",
                "contact_phone": "+91-40-5000-1021",
                "contact_email": "aamir.khan@tmrrn.org",
                "availability": "Available",
                "current_location": "Hyderabad",
                "status": "Active",
            },
            {
                "name": "Dr. Ananya Iyer",
                "organization_id": organizations[4].id,
                "division_id": divisions[1].id,
                "role": "Specialist",
                "skills": "medical,first aid,pediatrics,triage",
                "contact_phone": "+91-40-5000-1022",
                "contact_email": "ananya.iyer@tmrrn.org",
                "availability": "Available",
                "current_location": "Warangal",
                "status": "Active",
            },
            {
                "name": "Rahul Dev",
                "organization_id": organizations[4].id,
                "division_id": divisions[1].id,
                "role": "Worker",
                "skills": "medical support,first aid,patient transport",
                "contact_phone": "+91-40-5000-1023",
                "contact_email": "rahul.dev@tmrrn.org",
                "availability": "Available",
                "current_location": "Khammam",
                "status": "Active",
            },
            {
                "name": "Kiran Kumar",
                "organization_id": organizations[2].id,
                "division_id": divisions[2].id,
                "role": "Worker",
                "skills": "logistics,shelter setup,transport planning",
                "contact_phone": "+91-40-5000-1003",
                "contact_email": "kiran.kumar@ghmc.gov.in",
                "availability": "Available",
                "current_location": "Warangal",
                "status": "Active",
            },
            {
                "name": "Sowmya Rani",
                "organization_id": organizations[2].id,
                "division_id": divisions[2].id,
                "role": "Manager",
                "skills": "logistics,relief supply,transport routing,warehouse",
                "contact_phone": "+91-40-5000-1031",
                "contact_email": "sowmya.rani@ghmc.gov.in",
                "availability": "Available",
                "current_location": "Hyderabad",
                "status": "Active",
            },
            {
                "name": "Arjun Patel",
                "organization_id": organizations[2].id,
                "division_id": divisions[2].id,
                "role": "Worker",
                "skills": "logistics,inventory,shelter setup,distribution",
                "contact_phone": "+91-40-5000-1032",
                "contact_email": "arjun.patel@ghmc.gov.in",
                "availability": "Available",
                "current_location": "Nalgonda",
                "status": "Active",
            },
            {
                "name": "Bhavya Reddy",
                "organization_id": organizations[2].id,
                "division_id": divisions[2].id,
                "role": "Worker",
                "skills": "logistics,field supply,resource movement,coordination",
                "contact_phone": "+91-40-5000-1033",
                "contact_email": "bhavya.reddy@ghmc.gov.in",
                "availability": "Available",
                "current_location": "Karimnagar",
                "status": "Active",
            },
            {
                "name": "Madhavi Ch",
                "organization_id": organizations[0].id,
                "division_id": divisions[3].id,
                "role": "Manager",
                "skills": "communication,coordination,public safety",
                "contact_phone": "+91-40-5000-1004",
                "contact_email": "madhavi@tsdma.telangana.gov.in",
                "availability": "Available",
                "current_location": "Hyderabad",
                "status": "Active",
            },
            {
                "name": "Srinivas Goud",
                "organization_id": organizations[0].id,
                "division_id": divisions[3].id,
                "role": "Specialist",
                "skills": "communication,incident command,public alert,coordination",
                "contact_phone": "+91-40-5000-1041",
                "contact_email": "srinivas.goud@tsdma.telangana.gov.in",
                "availability": "Available",
                "current_location": "Hyderabad",
                "status": "Active",
            },
            {
                "name": "Priya Nair",
                "organization_id": organizations[0].id,
                "division_id": divisions[3].id,
                "role": "Worker",
                "skills": "communication,helpline,response coordination,documentation",
                "contact_phone": "+91-40-5000-1042",
                "contact_email": "priya.nair@tsdma.telangana.gov.in",
                "availability": "Available",
                "current_location": "Secunderabad",
                "status": "Active",
            },
            {
                "name": "Anil Teja",
                "organization_id": organizations[0].id,
                "division_id": divisions[3].id,
                "role": "Worker",
                "skills": "communication,control room,dispatch support,coordination",
                "contact_phone": "+91-40-5000-1043",
                "contact_email": "anil.teja@tsdma.telangana.gov.in",
                "availability": "Available",
                "current_location": "Warangal",
                "status": "Active",
            },
            {
                "name": "Asha Menon",
                "organization_id": organizations[3].id,
                "division_id": divisions[4].id,
                "role": "Manager",
                "skills": "relief,logistics,community support,coordination",
                "contact_phone": "+91-40-5000-1051",
                "contact_email": "asha.menon@redcross-telangana.org",
                "availability": "Available",
                "current_location": "Hyderabad",
                "status": "Active",
            },
            {
                "name": "Rahim Ali",
                "organization_id": organizations[3].id,
                "division_id": divisions[4].id,
                "role": "Worker",
                "skills": "relief,food distribution,shelter support,field response",
                "contact_phone": "+91-40-5000-1052",
                "contact_email": "rahim.ali@redcross-telangana.org",
                "availability": "Available",
                "current_location": "Khammam",
                "status": "Active",
            },
            {
                "name": "Keerthi Babu",
                "organization_id": organizations[3].id,
                "division_id": divisions[4].id,
                "role": "Worker",
                "skills": "relief,first aid,community outreach,shelter operations",
                "contact_phone": "+91-40-5000-1053",
                "contact_email": "keerthi.babu@redcross-telangana.org",
                "availability": "Available",
                "current_location": "Nizamabad",
                "status": "Active",
            },
            {
                "name": "Deepa Joseph",
                "organization_id": organizations[3].id,
                "division_id": divisions[4].id,
                "role": "Specialist",
                "skills": "relief,child support,community care,coordination",
                "contact_phone": "+91-40-5000-1054",
                "contact_email": "deepa.joseph@redcross-telangana.org",
                "availability": "Available",
                "current_location": "Warangal",
                "status": "Active",
            },
        ]
        staff_members = [upsert_staff(db, payload) for payload in staff_data]

        # Users
        users_data = [
            {
                "username": "admin",
                "email": "admin@aegishub.in",
                "hashed_password": get_password_hash("admin123"),
                "role": "admin",
                "organization_id": organizations[0].id,
                "division_id": divisions[3].id,
                "is_active": True,
            },
            {
                "username": "responder",
                "email": "responder@aegishub.in",
                "hashed_password": get_password_hash("responder123"),
                "role": "responder",
                "organization_id": organizations[1].id,
                "division_id": divisions[0].id,
                "is_active": True,
            },
            {
                "username": "viewer",
                "email": "viewer@aegishub.in",
                "hashed_password": get_password_hash("viewer123"),
                "role": "viewer",
                "organization_id": organizations[3].id,
                "division_id": None,
                "is_active": True,
            },
        ]

        # Add responder credentials for each staff member.
        for staff_member in staff_members:
            username = make_username(staff_member.name)
            users_data.append(
                {
                    "username": username,
                    "email": f"{username}@aegishub.in",
                    "hashed_password": get_password_hash("responder123"),
                    "role": "responder",
                    "organization_id": staff_member.organization_id,
                    "division_id": staff_member.division_id,
                    "is_active": True,
                }
            )

        for payload in users_data:
            upsert_user(db, payload)

        # Shelters
        shelters_data = [
            {
                "name": "Hyderabad City Relief Shelter",
                "organization_id": organizations[2].id,
                "longitude": 78.4867,
                "latitude": 17.3850,
                "address": "Secunderabad Parade Grounds, Hyderabad",
                "capacity": 900,
                "current_occupancy": 120,
                "type": "Emergency",
                "status": "Active",
                "contact_person": "Kiran Kumar",
                "contact_phone": "+91-40-5000-2001",
                "facilities": "Food, Water, Beds, Toilets, Medical Desk",
            },
            {
                "name": "Warangal Regional Shelter",
                "organization_id": organizations[0].id,
                "longitude": 79.5941,
                "latitude": 17.9689,
                "address": "Kakatiya University Grounds, Warangal",
                "capacity": 600,
                "current_occupancy": 80,
                "type": "Emergency",
                "status": "Active",
                "contact_person": "Madhavi Ch",
                "contact_phone": "+91-40-5000-2002",
                "facilities": "Food, Water, Beds, Child Support",
            },
            {
                "name": "Khammam Transit Shelter",
                "organization_id": organizations[3].id,
                "longitude": 80.1514,
                "latitude": 17.2473,
                "address": "District Stadium, Khammam",
                "capacity": 500,
                "current_occupancy": 60,
                "type": "Temporary",
                "status": "Active",
                "contact_person": "A. Sirisha",
                "contact_phone": "+91-40-5000-2003",
                "facilities": "Food Packs, Water, Blankets",
            },
        ]
        for payload in shelters_data:
            upsert_by_name(db, Shelter, payload)

        # Hospitals
        hospitals_data = [
            {
                "name": "Gandhi Hospital",
                "organization_id": organizations[4].id,
                "longitude": 78.4983,
                "latitude": 17.4399,
                "address": "Musheerabad, Secunderabad",
                "total_beds": 1200,
                "available_beds": 350,
                "icu_beds": 140,
                "available_icu": 35,
                "contact_phone": "+91-40-5000-3001",
                "specialties": "Trauma, Emergency, Surgery, Internal Medicine",
                "emergency_services": "24x7 Emergency, Ambulance, ICU",
            },
            {
                "name": "Warangal MGM Hospital",
                "organization_id": organizations[4].id,
                "longitude": 79.5941,
                "latitude": 17.9784,
                "address": "MGM Road, Warangal",
                "total_beds": 900,
                "available_beds": 260,
                "icu_beds": 90,
                "available_icu": 22,
                "contact_phone": "+91-40-5000-3002",
                "specialties": "Emergency, Trauma, Pediatrics",
                "emergency_services": "24x7 Emergency, ICU",
            },
            {
                "name": "Nizamabad Government Hospital",
                "organization_id": organizations[4].id,
                "longitude": 78.0941,
                "latitude": 18.6725,
                "address": "Collectorate Road, Nizamabad",
                "total_beds": 650,
                "available_beds": 190,
                "icu_beds": 55,
                "available_icu": 15,
                "contact_phone": "+91-40-5000-3003",
                "specialties": "Emergency, Medicine, General Surgery",
                "emergency_services": "Emergency Ward, ICU",
            },
        ]
        for payload in hospitals_data:
            upsert_by_name(db, Hospital, payload)

        # Resource centers
        resources_data = [
            {
                "name": "Hyderabad Central Relief Warehouse",
                "organization_id": organizations[2].id,
                "longitude": 78.4867,
                "latitude": 17.3850,
                "address": "Moosapet Logistics Hub, Hyderabad",
                "type": "Food, Water, Life Jackets, First Aid Kits",
                "inventory": "Rice,Water,Life Jackets,First Aid Kits,Blankets",
                "contact_person": "Ravi Teja",
                "contact_phone": "+91-40-5000-4001",
                "capacity": 2500,
                "current_stock": 1700,
            },
            {
                "name": "Warangal Medical Supply Depot",
                "organization_id": organizations[4].id,
                "longitude": 79.5941,
                "latitude": 17.9689,
                "address": "Hanamkonda Medical Stores Complex",
                "type": "Medicine, First Aid Kits, Oxygen Support",
                "inventory": "Bandages,Antibiotics,Painkillers,First Aid Kits,Oxygen Cylinders",
                "contact_person": "Dr. Sneha Reddy",
                "contact_phone": "+91-40-5000-4002",
                "capacity": 1800,
                "current_stock": 1100,
            },
        ]
        for payload in resources_data:
            upsert_by_name(db, ResourceCenter, payload)

        # Sample SOS ticket for immediate dashboard visibility
        sample_external = "APP-TEL-001"
        sample = db.query(SOSRequest).filter(SOSRequest.external_id == sample_external).first()
        if not sample:
            sample = SOSRequest(
                external_id=sample_external,
                status="Pending",
                people=23,
                longitude=79.5941,
                latitude=17.9689,
                text="Heavy rainfall caused waterlogging. Families trapped near low-lying colonies.",
                place="Warangal Urban",
                category="Flood Rescue",
                priority=5,
                assigned_to=staff_members[0].id,
                assigned_organization=organizations[1].id,
                assigned_division=divisions[0].id,
                notes="Autogenerated Telangana seed incident",
                assignment_time=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(sample)
        else:
            sample.status = "Pending Assignment"
            sample.assignment_time = datetime.utcnow()
            sample.updated_at = datetime.utcnow()

        db.commit()

        print("Database initialized successfully for Telangana.")
        print("Default credentials:")
        print(" - admin / admin123")
        print(" - responder / responder123")
        print(" - harish.rao / responder123")
        print(" - dr.sneha.reddy / responder123")
        print(" - kiran.kumar / responder123")
        print(" - madhavi.ch / responder123")
        print(" - viewer / viewer123")
        print(" - all seeded staff usernames / responder123")
    except Exception as exc:
        db.rollback()
        print(f"Initialization failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Initializing AegisHub Telangana database...")
    create_sample_data()
