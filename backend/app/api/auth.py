from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.auth.password import verify_password
from app.auth.jwt import create_access_token, get_current_user
from app.schemas.auth import LoginRequest, TokenResponse, UserMe
from app.models.user import User
from app.models.audit_log import AuditLog
from app.core.utils import utc_now

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.login == request.login))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")
    
    token = create_access_token(
        user_id=str(user.id),
        login=user.login,
        role=user.role,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    
    # Audit login
    audit = AuditLog(
        entity_type="User",
        entity_id=user.id,
        action="LOGIN",
        user_id=user.id,
        after_json={"login": user.login, "role": user.role},
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()
    
    return TokenResponse(
        access_token=token,
        expires_in=480,
        user=UserMe(
            id=user.id,
            login=user.login,
            role=user.role,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=f"{user.last_name} {user.first_name}",
        )
    )


@router.get("/me", response_model=UserMe)
async def me(current_user: UserMe = Depends(get_current_user)):
    return current_user


@router.post("/logout")
async def logout(
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(get_current_user),
):
    """Минимальный logout: записывает LOGOUT в audit_log. Токен не инвалидируется (см. SECURITY_AUDIT.md)."""
    audit = AuditLog(
        entity_type="User",
        entity_id=current_user.id,
        action="LOGOUT",
        user_id=current_user.id,
        after_json={"login": current_user.login},
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()
    return {"status": "ok"}


@router.post("/refresh")
async def refresh_placeholder():
    """Refresh tokens не реализованы в MVP — JWT живёт 8 часов (ACCESS_TOKEN_EXPIRE_MINUTES=480).

    Для полноценной реализации нужна отдельная таблица refresh_tokens (или поле в users),
    эндпоинт выдачи пары access/refresh, их хранение и ротация. См. ARCHITECTURE_DECISIONS.md.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Refresh tokens не реализованы в MVP. Перелогиньтесь для получения нового токена.",
    )
