from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    login: str = Field(..., min_length=3, max_length=50)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    role: str = Field(..., pattern="^(REGISTRAR|TECHNOLOGIST|RADIOLOGIST|HEAD|REFERRER|ADMIN)$")
    specialization: str | None = None
    license_number: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    role: str | None = None
    specialization: str | None = None
    license_number: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    id: UUID
    default_device_id: UUID | None = None
    created_at: datetime

    class Config:
        from_attributes = True
