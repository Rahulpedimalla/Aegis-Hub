from typing import Optional

from database import Division, Organization, Staff


def _normalize_org_status(org: Organization) -> None:
    load = max(0, int(org.current_load or 0))
    capacity = max(0, int(org.capacity or 0))
    org.current_load = load
    if capacity == 0:
        org.status = "Active"
        return
    if load >= capacity:
        org.status = "Overloaded"
    elif load > 0:
        org.status = "Active"
    else:
        org.status = "Available"


def _normalize_division_status(division: Division) -> None:
    load = max(0, int(division.current_load or 0))
    capacity = max(0, int(division.capacity or 0))
    division.current_load = load
    if capacity == 0:
        division.status = "Active"
        return
    if load >= capacity:
        division.status = "Overloaded"
    elif load > 0:
        division.status = "Active"
    else:
        division.status = "Available"


def _set_staff_assigned(staff: Staff, sos_id: Optional[str]) -> None:
    staff.availability = "Busy"
    if sos_id:
        staff.current_location = f"Assigned to SOS {sos_id}"


def _set_staff_released(staff: Staff) -> None:
    staff.availability = "Available"


def transfer_assignment_workload(
    db,
    old_org_id: Optional[str],
    old_division_id: Optional[str],
    old_staff_id: Optional[str],
    new_org_id: Optional[str],
    new_division_id: Optional[str],
    new_staff_id: Optional[str],
    sos_id: Optional[str] = None,
) -> None:
    """
    Move active workload counters/resources from old assignment to new assignment.
    Safe for partial changes and no-op when IDs are unchanged.
    """
    if old_org_id and old_org_id != new_org_id:
        old_org = db.query(Organization).filter(Organization.id == old_org_id).first()
        if old_org:
            old_org.current_load = max(0, int(old_org.current_load or 0) - 1)
            _normalize_org_status(old_org)

    if old_division_id and old_division_id != new_division_id:
        old_div = db.query(Division).filter(Division.id == old_division_id).first()
        if old_div:
            old_div.current_load = max(0, int(old_div.current_load or 0) - 1)
            _normalize_division_status(old_div)

    if old_staff_id and old_staff_id != new_staff_id:
        old_staff = db.query(Staff).filter(Staff.id == old_staff_id).first()
        if old_staff:
            _set_staff_released(old_staff)

    if new_org_id and new_org_id != old_org_id:
        new_org = db.query(Organization).filter(Organization.id == new_org_id).first()
        if new_org:
            new_org.current_load = int(new_org.current_load or 0) + 1
            _normalize_org_status(new_org)

    if new_division_id and new_division_id != old_division_id:
        new_div = db.query(Division).filter(Division.id == new_division_id).first()
        if new_div:
            new_div.current_load = int(new_div.current_load or 0) + 1
            _normalize_division_status(new_div)

    if new_staff_id and new_staff_id != old_staff_id:
        new_staff = db.query(Staff).filter(Staff.id == new_staff_id).first()
        if new_staff:
            _set_staff_assigned(new_staff, sos_id=sos_id)


def release_assignment_workload(
    db,
    organization_id: Optional[str],
    division_id: Optional[str],
    staff_id: Optional[str],
) -> None:
    """
    Release workload resources when an incident is completed/cancelled.
    """
    transfer_assignment_workload(
        db=db,
        old_org_id=organization_id,
        old_division_id=division_id,
        old_staff_id=staff_id,
        new_org_id=None,
        new_division_id=None,
        new_staff_id=None,
    )

