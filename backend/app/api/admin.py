import json
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from app.core.security import require_admin
from app.db.mongodb import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/export")
def export_attendance(_claims: dict = Depends(require_admin)):
    records = list(get_db().attendance.find({}, {"_id": 0}).sort("date", -1).limit(5000))
    payload = json.dumps(records, default=str, indent=2)
    return Response(content=payload, media_type="application/json", headers={"Content-Disposition": "attachment; filename=aurelix-attendance-export.json"})
