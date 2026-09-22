from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class VerificationRequest(BaseModel):
    action: Literal["check_in", "check_out"] = "check_in"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0, le=100000)
    source: Literal["browser"] | None = "browser"

class AttendanceResponse(BaseModel):
    success: bool
    status: str
    reason: str | None = None
    message: str | None = None
    timestamp: datetime | None = None

class AttendanceRecord(BaseModel):
    attendance_id: str
    employee_id: str
    user_name: str | None = None
    date: str
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    check_in_location: dict | None = None
    check_out_location: dict | None = None
    final_status: str
