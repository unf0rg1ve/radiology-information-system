"""
Машина состояний для Order (F2.3).
Явная таблица допустимых переходов из ТЗ раздел 7.

Основной поток:
  NEW → SCHEDULED → ARRIVED → IN_PROGRESS → ACQUIRED → TO_REPORT → REPORTING → SIGNED → ISSUED

Боковые переходы:
  Любой статус до IN_PROGRESS → CANCELLED (с указанием причины)
  ACQUIRED → IN_PROGRESS (при RETAKE)

Недопустимый переход → HTTP 422 с понятным русским сообщением.
"""

from app.models.order import OrderStatus


# Допустимые переходы: {из_статуса: {допустимые_целевые_статусы}}
VALID_TRANSITIONS = {
    OrderStatus.NEW: {OrderStatus.SCHEDULED, OrderStatus.CANCELLED},
    OrderStatus.SCHEDULED: {OrderStatus.ARRIVED, OrderStatus.CANCELLED},
    OrderStatus.ARRIVED: {OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED},
    OrderStatus.IN_PROGRESS: {OrderStatus.ACQUIRED, OrderStatus.CANCELLED},
    OrderStatus.ACQUIRED: {OrderStatus.TO_REPORT, OrderStatus.IN_PROGRESS},  # IN_PROGRESS при RETAKE
    OrderStatus.TO_REPORT: {OrderStatus.REPORTING},
    OrderStatus.REPORTING: {OrderStatus.SIGNED},
    OrderStatus.SIGNED: {OrderStatus.ISSUED},
    OrderStatus.ISSUED: {OrderStatus.REPORTING},  # правка выданного заключения создаёт новую версию
    OrderStatus.CANCELLED: set(),  # Конечный статус
}

# Человекочитаемые названия статусов на русском
STATUS_LABELS = {
    OrderStatus.NEW: "Новое",
    OrderStatus.SCHEDULED: "Запланировано",
    OrderStatus.ARRIVED: "Пациент прибыл",
    OrderStatus.IN_PROGRESS: "В процессе",
    OrderStatus.ACQUIRED: "Снимки получены",
    OrderStatus.TO_REPORT: "К описанию",
    OrderStatus.REPORTING: "Описание",
    OrderStatus.SIGNED: "Подписано",
    OrderStatus.ISSUED: "Выдано",
    OrderStatus.CANCELLED: "Отменено",
}

# Статусы, допускающие переход в CANCELLED
CANCEL_ALLOWED_FROM = {
    OrderStatus.NEW,
    OrderStatus.SCHEDULED,
    OrderStatus.ARRIVED,
    OrderStatus.IN_PROGRESS,
}


def _normalize(status):
    """Привести строку/enum к OrderStatus."""
    if isinstance(status, OrderStatus):
        return status
    return OrderStatus(status)


class InvalidStatusTransition(Exception):
    """Исключение при недопустимом переходе статуса."""

    def __init__(self, current_status: str, target_status: str):
        self.current_status = current_status
        self.target_status = target_status
        current = _normalize(current_status)
        target = _normalize(target_status)
        allowed = VALID_TRANSITIONS.get(current, set())
        allowed_labels = [STATUS_LABELS.get(s, s.value) for s in allowed]
        current_label = STATUS_LABELS.get(current, current.value)
        target_label = STATUS_LABELS.get(target, target.value)
        message = (
            f"Недопустимый переход статуса: '{current_label}' → '{target_label}'. "
            f"Допустимые переходы из '{current_label}': {', '.join(allowed_labels) if allowed_labels else 'нет (конечный статус)'}"
        )
        super().__init__(message)


def validate_status_transition(current_status: str, target_status: str) -> None:
    """
    Проверить допустимость перехода статуса.
    Бросает InvalidStatusTransition если переход недопустим.
    Принимает как строки, так и enum-значения OrderStatus.
    """
    current = _normalize(current_status)
    target = _normalize(target_status)

    if current == target:
        return  # Тот же статус — ок (idempotent)

    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStatusTransition(current_status, target_status)


def is_terminal_status(status: str) -> bool:
    """Проверить, является ли статус конечным (из него нет переходов)."""
    normalized = _normalize(status)
    return normalized in (OrderStatus.ISSUED, OrderStatus.CANCELLED)


def get_allowed_transitions(status: str) -> set[str]:
    """Получить допустимые целевые статусы из текущего."""
    normalized = _normalize(status)
    return VALID_TRANSITIONS.get(normalized, set())
