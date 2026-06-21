"""
Автоматический аудит-лог (Задача 6.1).

Через SQLAlchemy event listeners (after_insert, after_update) для ключевых сущностей.
Пишет entity_type, entity_id, action, user_id, before_json, after_json, timestamp.

Записи audit_log не должны быть удаляемы через API (нет DELETE эндпоинта).
"""
import logging
from datetime import datetime, date
from uuid import UUID
from sqlalchemy import event, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.core.utils import utc_now

logger = logging.getLogger(__name__)

# Entities to audit
AUDITED_MODELS = {}  # Will be populated after imports


def _model_to_dict(instance) -> dict:
    """Convert SQLAlchemy model instance to dict for audit logging."""
    if instance is None:
        return {}
    mapper = inspect(instance).mapper
    result = {}
    for column in mapper.columns:
        key = column.key
        try:
            value = getattr(instance, key)
            result[key] = json_safe(value)
        except Exception:
            continue
    return result


def json_safe(value):
    """Convert values to JSON-serializable form for audit_log JSON columns."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def get_audit_session():
    """Get the current request's user_id from context.

    This is a thread-local approach for storing the current user ID.
    In production, use proper request context middleware.
    """
    import contextvars
    _current_user_id = contextvars.ContextVar('current_user_id', default=None)
    return _current_user_id


# Context variable for current user ID in audit
_current_user_id_ctx = get_audit_session()


def set_audit_user(user_id):
    """Set the current user ID for audit logging."""
    _current_user_id_ctx.set(user_id)


def get_audit_user():
    """Get the current user ID for audit logging."""
    return _current_user_id_ctx.get()


def register_audit_listeners(engine, session_factory):
    """
    Register SQLAlchemy event listeners for automatic audit logging.
    Should be called after all models are imported.

    DEPRECATED: Эта функция больше не вызывается из main.py.

    Async SQLAlchemy session events для after_flush/before_commit не
    поддерживаются напрямую. Попытка зарегистрировать before_flush на
    AsyncSession не падает, но listener не срабатывает (события диспатчатся
    на sync_session). Поэтому автоматический аудит отключён, а аудит-лог
    реализован явными AuditLog(...) записями в API-эндпоинтах.

    Явные AuditLog записи добавлены в: auth.py (LOGIN/LOGOUT),
    patients.py (CREATE/UPDATE Patient), orders.py (CREATE/STATUS_UPDATE),
    reports.py (CREATE/UPDATE/SIGN/ISSUE/new-version/second-opinion,
    CITO_NOTIFICATION), admin.py (CREATE/UPDATE/PASSWORD_RESET/PASSWORD_CHANGE
    User), worklist.py (UNMATCHED_RESOLVED).
    """
    from app.models.patient import Patient
    from app.models.order import Order
    from app.models.report import Report
    from app.models.study import Study

    audited = {
        Patient: "Patient",
        Order: "Order",
        Report: "Report",
        Study: "Study",
    }

    try:
        @event.listens_for(AsyncSession, "before_flush")
        def before_flush(session, flush_context, instances):
            """Log audit entries before flush."""
            user_id = get_audit_user()

            for instance in session.new:
                model_class = type(instance)
                if model_class in audited:
                    # Skip AuditLog itself to avoid recursion
                    if model_class == AuditLog:
                        continue
                    audit = AuditLog(
                        entity_type=audited[model_class],
                        entity_id=instance.id if hasattr(instance, 'id') else None,
                        action="CREATE",
                        user_id=user_id,
                        before_json=None,
                        after_json=_model_to_dict(instance),
                        timestamp=utc_now(),
                    )
                    session.add(audit)

            for instance in session.dirty:
                model_class = type(instance)
                if model_class in audited:
                    if model_class == AuditLog:
                        continue
                    # Get before/after state
                    before = {}
                    after = {}
                    for attr in inspect(instance).attrs:
                        hist = attr.history
                        if hist.has_changes():
                            key = attr.key
                            before[key] = hist.deleted[0] if hist.deleted else None
                            after[key] = hist.added[0] if hist.added else None

                    if before or after:
                        audit = AuditLog(
                            entity_type=audited[model_class],
                            entity_id=instance.id if hasattr(instance, 'id') else None,
                            action="UPDATE",
                            user_id=user_id,
                            before_json=before,
                            after_json=after,
                            timestamp=utc_now(),
                        )
                        session.add(audit)

        logger.info("Audit event listeners registered for: %s", list(audited.values()))
    except Exception as e:
        logger.warning("Automatic audit listeners could not be registered: %s. Explicit audit logging in endpoints remains active.", e)
