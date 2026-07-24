from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC datetime for DB columns (replaces deprecated datetime.utcnow())."""
    return datetime.now(UTC).replace(tzinfo=None)
