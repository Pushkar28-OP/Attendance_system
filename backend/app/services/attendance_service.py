import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.db.mongodb import get_db
from app.models.attendance import attendance_document
from app.models.audit import audit_event
from app.services.geocoding_service import reverse_geocode_location


REASONS = {
    "ALREADY_CHECKED_IN": "You have already checked in today.",
    "NOT_CHECKED_IN": "You must check in before checking out.",
    "ALREADY_CHECKED_OUT": "You have already checked out today.",
}

logger = logging.getLogger(__name__)
KOLKATA_TIME_ZONE = ZoneInfo("Asia/Kolkata")


def _rejected(reason: str) -> dict:
    return {"success": False, "status": "REJECTED", "reason": reason, "message": REASONS.get(reason, "Attendance action was rejected."), "timestamp": datetime.now(timezone.utc)}


def _location(payload) -> dict | None:
    if payload.latitude is None or payload.longitude is None:
        return None
    location = {"latitude": payload.latitude, "longitude": payload.longitude, "source": getattr(payload, "source", None) or "browser"}
    if payload.accuracy is not None:
        location["accuracy"] = payload.accuracy
    resolved = reverse_geocode_location(payload.latitude, payload.longitude)
    if resolved:
        location.update(resolved)
    return location


def _record_audit_event(db, employee_id: str, action: str, location_available: bool) -> None:
    try:
        db.audit_logs.insert_one(
            audit_event(
                "SUCCESSFUL_ATTENDANCE",
                employee_id,
                "ACCEPTED",
                {"action": action, "location_available": location_available},
            )
        )
    except Exception:
        # Attendance has already been committed. An audit-log outage must not make it look unsuccessful.
        logger.exception("Attendance recorded but the audit event could not be saved")


def verify_and_record(employee: dict, payload) -> dict:
    db = get_db()
    employee_id = employee["employee_id"]
    now = datetime.now(timezone.utc)
    today = now.astimezone(KOLKATA_TIME_ZONE).date().isoformat()
    existing = db.attendance.find_one({"employee_id": employee_id, "date": today})
    if payload.action == "check_in" and existing and existing.get("check_in_time"):
        return _rejected("ALREADY_CHECKED_IN")
    if payload.action == "check_out" and (not existing or not existing.get("check_in_time")):
        return _rejected("NOT_CHECKED_IN")
    if payload.action == "check_out" and existing and existing.get("check_out_time"):
        return _rejected("ALREADY_CHECKED_OUT")
    location = _location(payload)
    if not existing:
        existing = attendance_document(employee_id, today, employee.get("full_name"))
        existing.update({"final_status": "PRESENT", "check_in_time": now, "check_in_location": location, "updated_at": now})
        try:
            db.attendance.insert_one(existing)
        except Exception:
            return _rejected("ALREADY_CHECKED_IN")
    elif payload.action == "check_in":
        db.attendance.update_one(
            {"_id": existing["_id"]},
            {"$set": {"user_name": existing.get("user_name") or employee.get("full_name"), "final_status": "PRESENT", "check_in_time": now, "check_in_location": location, "check_out_time": None, "check_out_location": None, "updated_at": now}},
        )
    else:
        db.attendance.update_one(
            {"_id": existing["_id"]},
            {"$set": {"user_name": existing.get("user_name") or employee.get("full_name"), "final_status": "PRESENT", "check_out_time": now, "check_out_location": location, "updated_at": now}},
        )
    _record_audit_event(db, employee_id, payload.action, location is not None)
    return {"success": True, "status": "PRESENT", "reason": None, "message": "Attendance recorded.", "timestamp": now}
