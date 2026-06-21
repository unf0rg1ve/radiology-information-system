from uuid import UUID
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserMe"


class UserMe(BaseModel):
    id: UUID
    login: str
    role: str
    first_name: str
    last_name: str
    middle_name: str | None = None
    full_name: str | None = None

    class Config:
        from_attributes = True


# Resolve forward reference
TokenResponse.model_rebuild()
