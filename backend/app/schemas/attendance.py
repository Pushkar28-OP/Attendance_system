from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class VerificationRequest(BaseModel):
    image: str = Field(min_length=20, description="Base64-encoded camera frame")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float = Field(gt=0, le=100000)
    action: Literal["check_in", "check_out"] = "check_in"
    liveness_frames: list[str] = Field(default_factory=list, max_length=8)

class AttendanceResponse(BaseModel):
    success: bool
    status: str
    reason: str | None = None
    message: str | None = None
    face_verified: bool = False
    liveness_verified: bool = False
    location_verified: bool = False
    face_match_score: float | None = None
    liveness_score: float | None = None
    office_distance: float | None = None
    location_diagnostics: dict | None = None
    timestamp: datetime | None = None

class AttendanceRecord(BaseModel):
    attendance_id: str
    employee_id: str
    date: str
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    face_match_score: float | None = None
    liveness_score: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy: float | None = None
    office_distance: float | None = None
    face_verification_status: str
    location_verification_status: str
    final_status: str
