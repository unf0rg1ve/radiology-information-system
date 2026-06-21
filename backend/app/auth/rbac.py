from enum import Enum
from fastapi import HTTPException, status, Depends
from app.auth.jwt import get_current_user
from app.schemas.auth import UserMe


class Role(str, Enum):
    REGISTRAR = "REGISTRAR"
    TECHNOLOGIST = "TECHNOLOGIST"
    RADIOLOGIST = "RADIOLOGIST"
    HEAD = "HEAD"
    REFERRER = "REFERRER"
    ADMIN = "ADMIN"


def require_roles(allowed_roles: list[str]):
    def role_checker(current_user: UserMe = Depends(get_current_user)) -> UserMe:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Доступ запрещен. Требуется одна из ролей: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


# Predefined role dependencies
registrar_only = require_roles([Role.REGISTRAR.value, Role.REFERRER.value, Role.ADMIN.value])
technologist_only = require_roles([Role.TECHNOLOGIST.value, Role.ADMIN.value])
radiologist_only = require_roles([Role.RADIOLOGIST.value, Role.HEAD.value])
head_only = require_roles([Role.HEAD.value, Role.ADMIN.value])
referrer_only = require_roles([Role.REFERRER.value, Role.ADMIN.value])
admin_only = require_roles([Role.ADMIN.value])
any_authenticated = get_current_user
