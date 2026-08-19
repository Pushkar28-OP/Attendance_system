from fastapi import APIRouter, Depends
from app.core.security import require_admin
from app.db.mongodb import get_db

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("")
def audit_logs(_claims: dict = Depends(require_admin)):
    return list(get_db().audit_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(300))
