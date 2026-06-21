from datetime import datetime, timedelta, timezone
from uuid import UUID
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import get_settings
from app.schemas.auth import UserMe

settings = get_settings()
security = HTTPBearer(auto_error=False)


def create_access_token(user_id: str, login: str, role: str, first_name: str, last_name: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "login": login,
        "role": role,
        "first_name": first_name,
        "last_name": last_name,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истекший токен",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserMe:
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Неверный токен")
    
    return UserMe(
        id=UUID(user_id),
        login=payload.get("login", ""),
        role=payload.get("role", ""),
        first_name=payload.get("first_name", ""),
        last_name=payload.get("last_name", ""),
        full_name=f"{payload.get('last_name', '')} {payload.get('first_name', '')}",
    )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    token: str | None = Query(None),
) -> UserMe:
    """Auth that accepts Bearer header OR ?token= query param (for PDF downloads)."""
    raw = credentials.credentials if credentials else (token or None)
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(raw)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Неверный токен")
    return UserMe(
        id=UUID(user_id),
        login=payload.get("login", ""),
        role=payload.get("role", ""),
        first_name=payload.get("first_name", ""),
        last_name=payload.get("last_name", ""),
        full_name=f"{payload.get('last_name', '')} {payload.get('first_name', '')}",
    )
