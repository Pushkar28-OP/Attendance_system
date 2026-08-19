from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError
from app.core.security import require_admin, hash_password
from app.db.mongodb import get_db
from app.models.employee import employee_document, public_employee
from app.models.audit import audit_event
from app.schemas.employee import EmployeeCreate

router = APIRouter(prefix="/api/employees", tags=["employees"])

@router.get("")
def list_employees(_claims: dict = Depends(require_admin)):
    return [public_employee(item) for item in get_db().employees.find({}, {"password_hash": 0, "face_embedding": 0}).sort("full_name", 1)]

@router.post("", status_code=201)
def create_employee(payload: EmployeeCreate, claims: dict = Depends(require_admin)):
    db = get_db()
    document = employee_document(payload.employee_id, payload.full_name, payload.email, payload.department, payload.role, hash_password(payload.password))
    try:
        db.employees.insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Employee ID or email already exists") from exc
    db.audit_logs.insert_one(audit_event("EMPLOYEE_CREATED", claims["sub"], "ACCEPTED", {"employee_id": payload.employee_id}))
    return public_employee(document)
