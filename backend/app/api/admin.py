from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.auth.rbac import admin_only, any_authenticated
from app.auth.password import hash_password, verify_password
from app.auth.jwt import get_current_user
from app.schemas.auth import UserMe
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.audit import json_safe
from app.core.utils import utc_now


class PasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


def _user_audit_after_json(user: User) -> dict:
    return {
        "login": user.login,
        "role": user.role,
        "last_name": user.last_name,
        "first_name": user.first_name,
        "middle_name": user.middle_name,
        "specialization": user.specialization,
        "license_number": user.license_number,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
    }


router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    role: str = Query(None),
    search: str = Query(None),
    is_active: bool = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        search_lower = f"%{search.lower()}%"
        query = query.where(
            func.lower(User.last_name + " " + User.first_name).like(search_lower) |
            func.lower(User.login).like(search_lower)
        )
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/users", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    # Check login uniqueness
    result = await db.execute(select(User).where(User.login == data.login))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Логин уже занят")
    
    user = User(
        login=data.login,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        middle_name=data.middle_name,
        role=data.role,
        specialization=data.specialization,
        license_number=data.license_number,
        email=data.email,
        phone=data.phone,
        is_active=data.is_active,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    audit = AuditLog(
        entity_type="User",
        entity_id=user.id,
        action="CREATE",
        user_id=current_user.id,
        after_json=json_safe(_user_audit_after_json(user)),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    update_data = data.model_dump(exclude_unset=True)
    before = {field: json_safe(getattr(user, field)) for field in update_data}
    for field, value in update_data.items():
        setattr(user, field, value)
    after = {field: json_safe(getattr(user, field)) for field in update_data}

    await db.flush()
    await db.refresh(user)

    audit = AuditLog(
        entity_type="User",
        entity_id=user.id,
        action="UPDATE",
        user_id=current_user.id,
        before_json=before,
        after_json=after,
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return user


@router.get("/audit")
async def get_audit_log(
    entity_type: str = Query(None),
    entity_id: UUID = Query(None),
    user_id: UUID = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    query = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "entity_type": log.entity_type,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "action": log.action,
            "user_id": str(log.user_id) if log.user_id else None,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "ip_address": log.ip_address,
        }
        for log in logs
    ]


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: UUID,
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    """Сброс пароля пользователя (ТЗ F6.5)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.password_hash = hash_password(data.new_password)
    await db.flush()

    audit = AuditLog(
        entity_type="User",
        entity_id=user.id,
        action="PASSWORD_RESET",
        user_id=current_user.id,
        after_json=json_safe({"login": user.login}),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return {"status": "password_reset"}


@router.post("/change-password")
async def change_password(
    data: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(get_current_user),
):
    """Смена собственного пароля (ТЗ F6.5)."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")

    user.password_hash = hash_password(data.new_password)
    await db.flush()

    audit = AuditLog(
        entity_type="User",
        entity_id=user.id,
        action="PASSWORD_CHANGE",
        user_id=current_user.id,
        after_json=json_safe({"login": user.login}),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return {"status": "password_changed"}


@router.get("/users/{user_id}/login-history")
async def get_login_history(
    user_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    """Журнал входов пользователя (ТЗ F6.5)."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == user_id, AuditLog.action == "LOGIN")
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "ip_address": log.ip_address,
            "session_id": log.session_id,
        }
        for log in logs
    ]
