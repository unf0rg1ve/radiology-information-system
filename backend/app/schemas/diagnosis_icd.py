from uuid import UUID
from pydantic import BaseModel


class DiagnosisICDResponse(BaseModel):
    id: UUID
    code: str
    name_ru: str
    name_kz: str | None = None
    chapter: str | None = None
    chapter_name_ru: str | None = None
    is_leaf: bool

    class Config:
        from_attributes = True
