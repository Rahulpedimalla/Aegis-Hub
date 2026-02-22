from typing import Optional

from database import Staff


def normalize_person(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _email_local_part(value: str) -> str:
    if "@" not in (value or ""):
        return value or ""
    return str(value).split("@", 1)[0]


def resolve_responder_staff(current_user, db) -> Optional[Staff]:
    """
    Best-effort mapping from authenticated responder user to a staff record.
    Priority:
    1) username ~= staff.name
    2) username ~= contact_email local part
    3) unique staff in same organization + division
    4) unique staff in same organization
    """
    if (current_user.role or "").lower() != "responder":
        return None

    username = (current_user.username or "").strip()
    username_norm = normalize_person(username.replace(".", " "))
    active_staff = db.query(Staff).filter(Staff.status == "Active").all()

    name_matches = [s for s in active_staff if normalize_person(s.name or "") == username_norm]
    if len(name_matches) == 1:
        return name_matches[0]

    email_matches = [
        s
        for s in active_staff
        if normalize_person(_email_local_part(s.contact_email or "")) == username_norm
    ]
    if len(email_matches) == 1:
        return email_matches[0]

    if current_user.organization_id and current_user.division_id:
        by_org_div = [
            s
            for s in active_staff
            if str(s.organization_id or "") == str(current_user.organization_id)
            and str(s.division_id or "") == str(current_user.division_id)
        ]
        if len(by_org_div) == 1:
            return by_org_div[0]

    if current_user.organization_id:
        by_org = [
            s
            for s in active_staff
            if str(s.organization_id or "") == str(current_user.organization_id)
        ]
        if len(by_org) == 1:
            return by_org[0]

    return None
