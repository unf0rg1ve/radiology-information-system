from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator
import re


class PatientBase(BaseModel):
    iin: str = Field(..., min_length=12, max_length=12)
    last_name: str = Field(..., max_length=100)
    first_name: str = Field(..., max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    birth_date: date
    gender: str = Field(..., pattern="^[MF]$")
    phone: str | None = None
    email: str | None = None
    benefit_category: str = Field(default="NONE", pattern="^(GOMBP|OSMS|DISABLED|NONE)$")
    document_type: str | None = None
    document_number: str | None = None
    notes: str | None = None

    @field_validator("iin")
    @classmethod
    def validate_iin(cls, v: str) -> str:
        if not re.match(r'^\d{12}$', v):
            raise ValueError("ИИН должен содержать ровно 12 цифр")
        # Extract birth date from IIN
        try:
            year_prefix = int(v[0:2])
            month = int(v[2:4])
            day = int(v[4:6])
            century = int(v[6])
            if century in [1, 2]:
                year = 1800 + year_prefix
            elif century in [3, 4]:
                year = 1900 + year_prefix
            elif century in [5, 6]:
                year = 2000 + year_prefix
            else:
                raise ValueError("Неверный ИИН: некорректный век")
            date(year, month, day)
        except ValueError:
            raise ValueError("ИИН не прошел проверку даты рождения")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if not v:
            return v
        digits = re.sub(r"\D", "", v)
        if len(digits) == 10:
            digits = "7" + digits
        if not re.match(r"^7\d{10}$", digits):
            raise ValueError("Неверный формат телефона. Ожидается +7 XXX XXX XX XX")
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    phone: str | None = None
    email: str | None = None
    benefit_category: str | None = None
    notes: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if not v:
            return v
        digits = re.sub(r"\D", "", v)
        if len(digits) == 10:
            digits = "7" + digits
        if not re.match(r"^7\d{10}$", digits):
            raise ValueError("Неверный формат телефона. Ожидается +7 XXX XXX XX XX")
        return v


class PatientResponse(PatientBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatientSearchResult(BaseModel):
    id: UUID
    iin: str
    full_name: str
    birth_date: date
    phone: str | None
    last_study: str | None = None
    benefit_category: str
    last_order_status: str | None = None
    last_order_arrived_at: datetime | None = None
