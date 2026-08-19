from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import current_employee
from app.core.security import create_access_token, verify_password
from app.db.mongodb import get_db
from app.models.employee import public_employee
from app.models.audit import audit_event
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    db = get_db()
    employee = db.employees.find_one({"email": payload.email.lower()})
    if not employee or not verify_password(payload.password, employee.get("password_hash", "")):
        db.audit_logs.insert_one(audit_event("LOGIN_FAILURE", employee.get("employee_id") if employee else None, "REJECTED"))
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not employee.get("is_active", True):
        raise HTTPException(status_code=403, detail="Employee account is inactive")
    db.audit_logs.insert_one(audit_event("LOGIN_SUCCESS", employee["employee_id"], "ACCEPTED"))
    return {"access_token": create_access_token(employee["employee_id"], employee["role"]), "user": public_employee(employee)}

@router.get("/me")
def me(employee: dict = Depends(current_employee)):
    return public_employee(employee)
