from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from app.api.deps import current_employee
from app.core.security import require_admin
from app.db.mongodb import get_db
from app.models.attendance import public_attendance
from app.schemas.attendance import AttendanceResponse, VerificationRequest
from app.services.attendance_service import verify_and_record

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

@router.post("/verify", response_model=AttendanceResponse)
def verify(payload: VerificationRequest, employee: dict = Depends(current_employee)):
    return verify_and_record(employee, payload)

@router.get("/mine")
def mine(employee: dict = Depends(current_employee)):
    return [public_attendance(item) for item in get_db().attendance.find({"employee_id": employee["employee_id"]}).sort("date", -1).limit(90)]

@router.get("/admin")
def all_attendance(_claims: dict = Depends(require_admin), date: str | None = Query(default=None), employee_id: str | None = Query(default=None), status: str | None = Query(default=None)):
    query = {key: value for key, value in (("date", date), ("employee_id", employee_id), ("final_status", status)) if value}
    records = []
    for item in get_db().attendance.find(query).sort("date", -1).limit(500):
        record = public_attendance(item)
        employee = get_db().employees.find_one({"employee_id": item["employee_id"]}, {"password_hash": 0, "face_embedding": 0})
        record["employee"] = {"full_name": employee.get("full_name"), "department": employee.get("department")} if employee else None
        records.append(record)
    return records

@router.get("/dashboard")
def dashboard(_claims: dict = Depends(require_admin)):
    today = datetime.now(timezone.utc).date().isoformat()
    db = get_db()
    total = db.employees.count_documents({"role": "employee", "is_active": True})
    present = db.attendance.count_documents({"date": today, "final_status": "PRESENT"})
    rejected = db.audit_logs.count_documents({"event_type": {"$in": ["FACE_VERIFICATION_FAILURE", "LIVENESS_FAILURE", "LOCATION_VERIFICATION_FAILURE"]}, "created_at": {"$gte": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)}})
    return {"total_employees": total, "present_today": present, "absent_today": max(total - present, 0), "late_today": 0, "rejected_attempts": rejected}
