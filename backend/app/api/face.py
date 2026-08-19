from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.deps import current_employee
from app.core.security import require_admin
from app.db.mongodb import get_db
from app.models.audit import audit_event
from app.services.face_service import face_service

router = APIRouter(prefix="/api/face", tags=["face"])

class FaceRegistration(BaseModel):
    employee_id: str
    image: str = Field(min_length=20)

@router.post("/register")
def register_face(payload: FaceRegistration, _claims: dict = Depends(require_admin)):
    db = get_db()
    employee = db.employees.find_one({"employee_id": payload.employee_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        result = face_service.extract(payload.image)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.employees.update_one({"employee_id": payload.employee_id}, {"$set": {"face_embedding": result.embedding}})
    db.audit_logs.insert_one(audit_event("FACE_REGISTRATION", payload.employee_id, "ACCEPTED", {"quality": result.quality_score}))
    return {"success": True, "quality_score": result.quality_score}

@router.get("/status")
def face_status(employee: dict = Depends(current_employee)):
    return {"registered": bool(employee.get("face_embedding"))}
