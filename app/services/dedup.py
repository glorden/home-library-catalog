import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Edition

TITLE_SIMILARITY_THRESHOLD = 0.3  # = дефолтный GUC pg_trgm.similarity_threshold
MAX_CANDIDATES = 5
MIN_TRIGRAM_TITLE_LENGTH = 3

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_ISBN_NON_DIGITS_RE = re.compile(r"[^0-9Xx]")


def normalize_text(value: str) -> str:
    """NFKC + lower + ё→е + без пунктуации, для точного совпадения fingerprint.

    \\w уже unicode-aware в Python (без re.UNICODE тоже, он тут для ясности) —
    дореформенные буквы (ѣ, і, ѳ, ъ) остаются буквами, а не режутся как символы.

    Пунктуация заменяется на пробел, а не вырезается: иначе "Толстой Л.Н."
    (инициалы слитно) и "Толстой Л. Н." (инициалы через пробел) давали бы
    разные fingerprint — "л.н." без пробела-разделителя склеился бы в "лн" и
    перестал совпадать с "л н" из варианта с пробелом. Это реальный случай
    для авторских инициалов, а не гипотетический.
    """
    value = unicodedata.normalize("NFKC", value).lower().replace("ё", "е")
    value = _PUNCT_RE.sub(" ", value)
    return _WS_RE.sub(" ", value).strip()


def compute_fingerprint(title: str, authors: str | None, year: int | None) -> str:
    norm_title = normalize_text(title)
    norm_author = normalize_text(authors) if authors else ""
    year_part = str(year) if year is not None else ""
    return f"{norm_title}|{norm_author}|{year_part}"


def apply_fingerprint(edition: Edition) -> None:
    edition.dedup_fingerprint = compute_fingerprint(
        edition.title, edition.authors, edition.publication_year
    )


@dataclass
class DedupCandidate:
    edition: Edition
    reason: str  # "isbn" | "fingerprint" | "title_similarity"


def find_candidates(
    session: Session,
    *,
    title: str,
    authors: str | None,
    year: int | None,
    isbn: str | None,
    exclude_edition_id: int | None = None,
) -> list[DedupCandidate]:
    """Кандидаты на дубликат по трём сигналам (ARCHITECTURE.md): точный ISBN,
    точный fingerprint, похожесть title по pg_trgm. Только предлагаются
    вызывающей стороне — автослияния нет, сохранение ничем не блокируется."""
    if not title or not title.strip():
        return []

    def _exclude(stmt):
        if exclude_edition_id is not None:
            return stmt.where(Edition.id != exclude_edition_id)
        return stmt

    candidates: dict[int, DedupCandidate] = {}

    normalized_isbn = _ISBN_NON_DIGITS_RE.sub("", isbn) if isbn else ""
    if normalized_isbn:
        isbn_expr = func.regexp_replace(Edition.isbn, "[^0-9Xx]", "", "g")
        stmt = _exclude(select(Edition).where(isbn_expr == normalized_isbn))
        for edition in session.exec(stmt).all():
            candidates.setdefault(edition.id, DedupCandidate(edition, "isbn"))

    fingerprint = compute_fingerprint(title, authors, year)
    stmt = _exclude(select(Edition).where(Edition.dedup_fingerprint == fingerprint))
    for edition in session.exec(stmt).all():
        candidates.setdefault(edition.id, DedupCandidate(edition, "fingerprint"))

    # Лёгкая нормализация (только lower), НЕ compute_fingerprint: должна
    # соответствовать тому, что реально проиндексировано (lower(title)) —
    # pg_trgm и так толерантен к мелким отличиям по своей природе.
    lowered_title = title.strip().lower()
    if len(lowered_title) >= MIN_TRIGRAM_TITLE_LENGTH:
        similarity_expr = func.similarity(func.lower(Edition.title), lowered_title)
        stmt = (
            select(Edition)
            .where(similarity_expr > TITLE_SIMILARITY_THRESHOLD)
            .order_by(similarity_expr.desc())
            .limit(MAX_CANDIDATES)
        )
        stmt = _exclude(stmt)
        for edition in session.exec(stmt).all():
            candidates.setdefault(edition.id, DedupCandidate(edition, "title_similarity"))

    return list(candidates.values())[:MAX_CANDIDATES]
