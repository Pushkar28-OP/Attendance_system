from datetime import datetime, timezone
from uuid import uuid4


def attendance_document(employee_id: str, date: str, user_name: str | None = None) -> dict:
    now = datetime.now(timezone.utc)
    return {"attendance_id": str(uuid4()), "employee_id": employee_id, "user_name": user_name, "date": date, "check_in_time": None, "check_in_location": None, "check_out_time": None, "check_out_location": None, "final_status": "PENDING", "created_at": now, "updated_at": now}


def _utc_datetime(value):
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def public_attendance(document: dict) -> dict:
    record = {key: document.get(key) for key in ("attendance_id", "employee_id", "user_name", "date", "check_in_time", "check_out_time", "check_in_location", "check_out_location", "final_status")}
    record["check_in_time"] = _utc_datetime(record["check_in_time"])
    record["check_out_time"] = _utc_datetime(record["check_out_time"])
    return record
