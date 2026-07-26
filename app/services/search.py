from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Copy, Edition, Photo

DEFAULT_LIMIT = 50


def search_editions(
    session: Session, query: str, *, public_only: bool, limit: int = DEFAULT_LIMIT
) -> list[Edition]:
    """Полнотекстовый поиск по editions.search_vector (websearch_to_tsquery,
    'russian') с ранжированием по ts_rank. public_only=True — только издания
    хотя бы с одним публичным экземпляром (для витрины); используется
    Edition.id.in_(...) вместо JOIN Copy + DISTINCT — иначе DISTINCT
    конфликтует с ORDER BY ts_rank(...), которого нет в списке SELECT."""
    stmt = select(Edition)
    if public_only:
        visible_ids = select(Copy.edition_id).where(Copy.is_public.is_(True))
        stmt = stmt.where(Edition.id.in_(visible_ids))

    q = query.strip()
    if q:
        tsquery = func.websearch_to_tsquery("russian", q)
        stmt = stmt.where(Edition.search_vector.op("@@")(tsquery))
        stmt = stmt.order_by(func.ts_rank(Edition.search_vector, tsquery).desc())
    else:
        # Пустой q даёт пустой tsquery, который не матчит вообще ничего —
        # значит "без запроса" нужно обрабатывать отдельной веткой, а не
        # просто передавать '' в websearch_to_tsquery.
        stmt = stmt.order_by(Edition.title)

    return session.exec(stmt.limit(limit)).all()


def covers_for_editions(session: Session, editions: list[Edition]) -> dict[int, Photo]:
    """Обложка первого найденного ПУБЛИЧНОГО экземпляра на издание, одним
    батч-запросом (не N+1). Единственный вызывающий — публичная витрина,
    поэтому без параметра public_only: у него сегодня нет и не планируется
    этим шагом второго вызывающего с другой семантикой видимости."""
    covers: dict[int, Photo] = {}
    if not editions:
        return covers
    edition_ids = [edition.id for edition in editions]
    public_copies = session.exec(
        select(Copy).where(Copy.edition_id.in_(edition_ids), Copy.is_public.is_(True))
    ).all()
    copy_to_edition = {copy.id: copy.edition_id for copy in public_copies}
    copy_ids = list(copy_to_edition)
    if copy_ids:
        photos = session.exec(
            select(Photo).where(Photo.copy_id.in_(copy_ids), Photo.kind == "cover")
        ).all()
        for photo in photos:
            covers.setdefault(copy_to_edition[photo.copy_id], photo)
    return covers
