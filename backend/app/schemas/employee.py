from typing import Literal
from pydantic import BaseModel, EmailStr, Field

class EmployeeCreate(BaseModel):
    employee_id: str = Field(min_length=2, max_length=32)
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    department: str = Field(min_length=2, max_length=80)
    role: Literal["employee", "admin"] = "employee"
    password: str

class EmployeeUpdate(BaseModel):
    employee_id: str = Field(min_length=2, max_length=32)
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    department: str = Field(min_length=2, max_length=80)
    role: Literal["employee", "admin"] = "employee"
    password: str | None = None

class EmployeeResponse(BaseModel):
    id: str
    employee_id: str
    full_name: str
    email: str
    department: str
    role: str
    is_active: bool
    has_face_registered: bool
