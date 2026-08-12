import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


_SELECT_PATTERN = re.compile(r"^select\b", re.IGNORECASE)


def normalize_read_only_query(query: str) -> str | None:
    """Accept one plain SELECT statement and reject ambiguous SQL forms."""
    candidate = query.strip()
    if candidate.endswith(";"):
        candidate = candidate[:-1].rstrip()
    if not candidate or ";" in candidate:
        return None
    if not _SELECT_PATTERN.match(candidate):
        return None
    return candidate


async def enforce_read_only_transaction(db: AsyncSession) -> None:
    """Ask PostgreSQL to reject writes, including writes hidden in functions."""
    await db.execute(text("SET TRANSACTION READ ONLY"))
