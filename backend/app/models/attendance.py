from datetime import datetime, timezone
from uuid import uuid4


def attendance_document(employee_id: str, date: str) -> dict:
    now = datetime.now(timezone.utc)
    return {"attendance_id": str(uuid4()), "employee_id": employee_id, "date": date, "check_in_time": None, "check_out_time": None, "face_match_score": None, "liveness_score": None, "latitude": None, "longitude": None, "location_accuracy": None, "office_distance": None, "face_verification_status": "PENDING", "location_verification_status": "PENDING", "final_status": "PENDING", "created_at": now, "updated_at": now}


def public_attendance(document: dict) -> dict:
    return {key: document.get(key) for key in ("attendance_id", "employee_id", "date", "check_in_time", "check_out_time", "face_match_score", "liveness_score", "latitude", "longitude", "location_accuracy", "office_distance", "face_verification_status", "location_verification_status", "final_status")}
