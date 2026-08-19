from datetime import datetime, timezone
from app.core.config import get_settings
from app.db.mongodb import get_db
from app.models.attendance import attendance_document
from app.models.audit import audit_event
from app.services.face_service import face_service
from app.services.liveness_service import verify_liveness
from app.services.location_service import verify_location


REASONS = {
    "NO_FACE": "Face verification failed.",
    "FACE_MISMATCH": "Face verification failed.",
    "LIVENESS_FAILED": "Liveness verification failed. Please follow the camera prompt.",
    "LOCATION_ACCURACY_INSUFFICIENT": "Location accuracy is insufficient. Please try again.",
    "LOCATION_OUTSIDE_GEOFENCE": "Please move into the Aurelix office location.",
    "OFFICE_LOCATION_NOT_CONFIGURED": "Office location is not configured.",
    "ALREADY_CHECKED_IN": "You have already checked in today.",
    "NOT_CHECKED_IN": "You must check in before checking out.",
}


def _rejected(reason: str, face_score=None, liveness_score=None, distance=None, location_diagnostics=None) -> dict:
    return {"success": False, "status": "REJECTED", "reason": reason, "message": REASONS.get(reason, "Attendance verification was rejected."), "face_verified": False, "liveness_verified": False, "location_verified": False, "face_match_score": face_score, "liveness_score": liveness_score, "office_distance": distance, "location_diagnostics": location_diagnostics, "timestamp": datetime.now(timezone.utc)}


def verify_and_record(employee: dict, payload) -> dict:
    db = get_db()
    employee_id = employee["employee_id"]
    today = datetime.now(timezone.utc).date().isoformat()
    existing = db.attendance.find_one({"employee_id": employee_id, "date": today})
    if payload.action == "check_in" and existing and existing.get("check_in_time"):
        return _rejected("ALREADY_CHECKED_IN")
    if payload.action == "check_out" and (not existing or not existing.get("check_in_time")):
        return _rejected("NOT_CHECKED_IN")
    try:
        captured = face_service.extract(payload.image)
        stored = employee.get("face_embedding")
        if not stored:
            return _rejected("NO_FACE")
        face_score = face_service.similarity(captured.embedding, stored)
    except (ValueError, RuntimeError):
        db.audit_logs.insert_one(audit_event("FACE_VERIFICATION_FAILURE", employee_id, "REJECTED"))
        return _rejected("NO_FACE")
    if face_score < get_settings().face_match_threshold:
        db.audit_logs.insert_one(audit_event("FACE_VERIFICATION_FAILURE", employee_id, "REJECTED", {"score": round(face_score, 4)}))
        return _rejected("FACE_MISMATCH", face_score=face_score)
    live, liveness_score = verify_liveness(payload.liveness_frames, captured.embedding)
    if not live:
        db.audit_logs.insert_one(audit_event("LIVENESS_FAILURE", employee_id, "REJECTED"))
        return _rejected("LIVENESS_FAILED", face_score, liveness_score)
    settings = get_settings()
    location_ok, distance, location_reason = verify_location(payload.latitude, payload.longitude, payload.accuracy)
    location_diagnostics = {"browser_latitude": payload.latitude, "browser_longitude": payload.longitude, "accuracy_meters": payload.accuracy, "office_latitude": settings.office_latitude, "office_longitude": settings.office_longitude, "distance_meters": distance, "status": "INSIDE" if location_ok else "OUTSIDE"}
    if not location_ok:
        db.audit_logs.insert_one(audit_event("LOCATION_VERIFICATION_FAILURE", employee_id, "REJECTED", {"distance": distance, "accuracy": payload.accuracy}))
        return _rejected(location_reason or "LOCATION_OUTSIDE_GEOFENCE", face_score, liveness_score, distance, location_diagnostics)
    now = datetime.now(timezone.utc)
    if not existing:
        existing = attendance_document(employee_id, today)
        existing.update({"face_match_score": face_score, "liveness_score": liveness_score, "latitude": payload.latitude, "longitude": payload.longitude, "location_accuracy": payload.accuracy, "office_distance": distance, "face_verification_status": "VERIFIED", "location_verification_status": "VERIFIED", "final_status": "PRESENT", "check_in_time": now, "updated_at": now})
        try:
            db.attendance.insert_one(existing)
        except Exception:
            return _rejected("ALREADY_CHECKED_IN")
    else:
        existing.update({"check_out_time": now, "updated_at": now})
        db.attendance.replace_one({"_id": existing["_id"]}, existing)
    db.audit_logs.insert_one(audit_event("SUCCESSFUL_ATTENDANCE", employee_id, "ACCEPTED", {"action": payload.action, "distance": round(distance, 2)}))
    return {"success": True, "status": "PRESENT", "reason": None, "message": "Attendance confirmed.", "face_verified": True, "liveness_verified": True, "location_verified": True, "face_match_score": face_score, "liveness_score": liveness_score, "office_distance": distance, "location_diagnostics": location_diagnostics, "timestamp": now}
