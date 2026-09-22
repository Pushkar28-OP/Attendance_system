from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import current_employee
from app.core.security import require_admin
from app.db.mongodb import get_db
from app.models.attendance import public_attendance
from app.models.audit import audit_event
from app.schemas.attendance import AttendanceResponse, VerificationRequest
from app.services.attendance_service import verify_and_record

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

@router.post("/verify", response_model=AttendanceResponse)
def verify(payload: VerificationRequest, employee: dict = Depends(current_employee)):
    return verify_and_record(employee, payload)

@router.get("/mine")
def mine(employee: dict = Depends(current_employee)):
    db = get_db()
    records = []
    for item in db.attendance.find({"employee_id": employee["employee_id"]}).sort("date", -1).limit(90):
        if not item.get("check_in_time") and item.get("check_out_time"):
            db.attendance.update_one(
                {"_id": item["_id"]},
                {"$set": {"check_out_time": None, "check_out_location": None, "final_status": "ABSENT", "updated_at": datetime.now(timezone.utc)}},
            )
            item["check_out_time"] = None
            item["check_out_location"] = None
            item["final_status"] = "ABSENT"
        records.append(public_attendance(item))
    return records

@router.delete("/mine/{attendance_id}")
def undo_mine(attendance_id: str, action: str = Query("record", pattern=r"^(check_in|check_out|record)$"), employee: dict = Depends(current_employee)):
    db = get_db()
    record = db.attendance.find_one({"attendance_id": attendance_id, "employee_id": employee["employee_id"]})
    if not record:
        raise HTTPException(status_code=404, detail="Your attendance record was not found")
    if action == "record":
        db.attendance.delete_one({"_id": record["_id"]})
    else:
        changes = {"updated_at": datetime.now(timezone.utc)}
        if action == "check_in":
            changes.update({"check_in_time": None, "check_in_location": None, "check_out_time": None, "check_out_location": None, "final_status": "ABSENT"})
        elif not record.get("check_out_time"):
            raise HTTPException(status_code=400, detail="No check-out time is recorded")
        else:
            changes.update({"check_out_time": None, "check_out_location": None, "final_status": "PRESENT"})
        db.attendance.update_one({"_id": record["_id"]}, {"$set": changes})
    db.audit_logs.insert_one(audit_event("EMPLOYEE_ATTENDANCE_UNDO", employee["employee_id"], "ACCEPTED", {"attendance_id": attendance_id, "date": record["date"], "action": action}))
    return {"message": f"Your {action.replace('_', '-')} was undone", "attendance_id": attendance_id, "action": action}

@router.get("/admin")
def all_attendance(_claims: dict = Depends(require_admin), date: str | None = Query(default=None), employee_id: str | None = Query(default=None), status: str | None = Query(default=None)):
    query = {key: value for key, value in (("date", date), ("employee_id", employee_id), ("final_status", status)) if value}
    records = []
    db = get_db()
    for item in db.attendance.find(query).sort("date", -1).limit(500):
        record = public_attendance(item)
        employee = db.employees.find_one({"employee_id": item["employee_id"]}, {"password_hash": 0})
        record["employee"] = {"full_name": employee.get("full_name"), "department": employee.get("department")} if employee else None
        records.append(record)
    if date and not employee_id:
        existing = {item["employee_id"] for item in records}
        for employee in db.employees.find({"role": "employee", "is_active": True}, {"password_hash": 0}).sort("full_name", 1):
            if employee["employee_id"] in existing:
                continue
            records.append({"attendance_id": f"absent-{employee['employee_id']}-{date}", "employee_id": employee["employee_id"], "user_name": employee.get("full_name"), "date": date, "check_in_time": None, "check_in_location": None, "check_out_time": None, "check_out_location": None, "final_status": "ABSENT", "employee": {"full_name": employee["full_name"], "department": employee.get("department", "")}})
        records.sort(key=lambda item: item["employee"].get("full_name", ""))
    return records

@router.get("/admin/month")
def attendance_month(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"), _claims: dict = Depends(require_admin)):
    year, month_number = month.split("-", 1)
    records = get_db().attendance.find({"date": {"$regex": f"^{year}-{month_number}-"}}, {"_id": 0, "employee_id": 1, "date": 1, "final_status": 1})
    return list(records)

@router.delete("/admin/{attendance_id}")
def clear_attendance(attendance_id: str, claims: dict = Depends(require_admin)):
    db = get_db()
    record = db.attendance.find_one({"attendance_id": attendance_id})
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    db.attendance.delete_one({"_id": record["_id"]})
    db.audit_logs.insert_one(audit_event("ATTENDANCE_RECORD_CLEARED", claims["sub"], "ACCEPTED", {"attendance_id": attendance_id, "employee_id": record["employee_id"], "date": record["date"]}))
    return {"message": "Attendance record cleared", "attendance_id": attendance_id}

@router.get("/dashboard")
def dashboard(_claims: dict = Depends(require_admin)):
    today = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
    db = get_db()
    total = db.employees.count_documents({"role": "employee", "is_active": True})
    present = db.attendance.count_documents({"date": today, "final_status": "PRESENT"})
    return {"total_employees": total, "present_today": present, "absent_today": max(total - present, 0), "late_today": 0, "rejected_attempts": 0}
