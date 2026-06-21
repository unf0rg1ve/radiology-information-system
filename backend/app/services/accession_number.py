"""
Атомарная генерация Accession Number (Задача 2.3).

Формат: YYMMDD-NNNNN
Где NNNNN — атомарный счётчик на (org_id, дата), реализованный через
PostgreSQL advisory lock для single-instance MVP.

Альтернатива: отдельная таблица-последовательность с SELECT ... FOR UPDATE.
Оба подхода гарантируют отсутствие коллизий при параллельных запросах.
"""
import logging
from datetime import datetime
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def generate_accession_number(db: AsyncSession, org_id: UUID | None = None) -> str:
    """
    Атомарная генерация Accession Number.
    Формат: YYMMDD-NNNNN

    Использует PostgreSQL advisory lock для сериализации:
    - Хэш от (org_id, дата) → bigint для pg_advisory_xact_lock
    - Внутри транзакции: SELECT MAX(accession_number) ... FOR UPDATE → +1
    - При коллизии (редкий случай) — retry с incremented sequence
    """
    now = datetime.now()
    date_part = now.strftime("%y%m%d")

    # Use advisory lock scoped to (org_id, date)
    # Generate a stable lock key from org_id + date
    org_part = str(org_id) if org_id else "default"
    lock_key_str = f"{org_part}:{date_part}"

    # Hash to int for advisory lock (PostgreSQL requires int8)
    lock_key = _hash_to_int64(lock_key_str)

    # Acquire transaction-level advisory lock
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})

    # Find max sequence for today within this org
    prefix = f"{date_part}-"
    if org_id:
        result = await db.execute(
            text(
                """
                SELECT MAX(accession_number) as max_an
                FROM orders
                WHERE accession_number LIKE :prefix
                  AND org_id = :org_id
                """
            ),
            {"prefix": f"{prefix}%", "org_id": str(org_id)},
        )
    else:
        result = await db.execute(
            text(
                """
                SELECT MAX(accession_number) as max_an
                FROM orders
                WHERE accession_number LIKE :prefix
                """
            ),
            {"prefix": f"{prefix}%"},
        )
    row = result.fetchone()

    if row and row.max_an:
        # Extract the NNNN part and increment
        try:
            current_seq = int(row.max_an.split("-")[1])
            next_seq = current_seq + 1
        except (IndexError, ValueError):
            # Fallback: use timestamp-based sequence
            next_seq = int(now.strftime("%H%M%S")) % 100000
            logger.warning(f"Could not parse sequence from AN {row.max_an}, using fallback: {next_seq}")
    else:
        # First order of the day
        next_seq = 1

    # Format: YYMMDD-NNNNN (5 digits zero-padded)
    accession_number = f"{prefix}{next_seq:05d}"

    # Verify uniqueness (safety check)
    check = await db.execute(
        text("SELECT 1 FROM orders WHERE accession_number = :an"),
        {"an": accession_number},
    )
    if check.fetchone():
        # Collision detected — increment until unique
        for _ in range(100):
            next_seq += 1
            accession_number = f"{prefix}{next_seq:05d}"
            check = await db.execute(
                text("SELECT 1 FROM orders WHERE accession_number = :an"),
                {"an": accession_number},
            )
            if not check.fetchone():
                break
        else:
            raise RuntimeError(f"Не удалось сгенерировать уникальный Accession Number после 100 попыток для даты {date_part}")

    return accession_number


def _hash_to_int64(s: str) -> int:
    """Convert string to a stable int64 for PostgreSQL advisory lock."""
    import hashlib
    h = hashlib.sha256(s.encode()).digest()
    # Take first 8 bytes and convert to int64 (ensure positive)
    val = int.from_bytes(h[:8], byteorder="big")
    # Ensure it fits in int64 range and is positive
    return val % (2**63 - 1)
