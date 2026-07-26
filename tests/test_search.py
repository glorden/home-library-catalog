from sqlmodel import select

from app.config import settings
from app.models import Copy


def _create_edition(db_client, title: str, **extra) -> int:
    data = {"title": title, **extra}
    response = db_client.post("/admin/editions", data=data, follow_redirects=False)
    return int(response.headers["location"].rsplit("/", 1)[-1])


def _make_public(db_client, edition_id: int) -> None:
    db_client.post(
        f"/admin/editions/{edition_id}/copies", data={"is_public": "true"}, follow_redirects=False
    )


def _make_private(db_client, session, edition_id: int) -> None:
    db_client.post(f"/admin/editions/{edition_id}/copies", data={}, follow_redirects=False)
    copy = session.exec(select(Copy).where(Copy.edition_id == edition_id)).one()
    copy.is_public = False
    session.add(copy)
    session.commit()


def test_admin_search_finds_by_partial_title(db_client):
    _create_edition(db_client, "Война и мир", authors="Толстой Лев Николаевич")
    _create_edition(db_client, "Дети капитана Гранта", authors="Верн Жюль")

    response = db_client.get("/admin/editions", params={"q": "война"})

    assert "Война и мир" in response.text
    assert "Дети капитана Гранта" not in response.text


def test_admin_search_finds_by_author(db_client):
    _create_edition(db_client, "Война и мир", authors="Толстой Лев Николаевич")
    _create_edition(db_client, "Дети капитана Гранта", authors="Верн Жюль")

    response = db_client.get("/admin/editions", params={"q": "толстой"})

    assert "Война и мир" in response.text
    assert "Дети капитана Гранта" not in response.text


def test_admin_search_includes_private_editions(db_client, session):
    private_id = _create_edition(db_client, "Секретный дневник")
    _make_private(db_client, session, private_id)

    response = db_client.get("/admin/editions", params={"q": "секретный"})

    assert "Секретный дневник" in response.text


def test_admin_empty_query_returns_full_list(db_client):
    _create_edition(db_client, "Война и мир")
    _create_edition(db_client, "Дети капитана Гранта")

    response = db_client.get("/admin/editions", params={"q": ""})

    assert "Война и мир" in response.text
    assert "Дети капитана Гранта" in response.text


def test_public_search_finds_public_edition_by_title(db_client):
    public_id = _create_edition(db_client, "Война и мир")
    _make_public(db_client, public_id)
    other_id = _create_edition(db_client, "Дети капитана Гранта")
    _make_public(db_client, other_id)

    response = db_client.get("/", params={"q": "война"})

    assert "Война и мир" in response.text
    assert "Дети капитана Гранта" not in response.text


def test_public_search_excludes_private_editions(db_client, session):
    private_id = _create_edition(db_client, "Секретный дневник")
    _make_private(db_client, session, private_id)

    response = db_client.get("/", params={"q": "секретный"})

    assert "Секретный дневник" not in response.text


def test_public_empty_query_returns_full_public_list(db_client):
    public_id = _create_edition(db_client, "Война и мир")
    _make_public(db_client, public_id)

    response = db_client.get("/", params={"q": ""})

    assert "Война и мир" in response.text


def test_public_search_respects_showcase_closed(db_client, monkeypatch):
    monkeypatch.setattr(settings, "showcase_public", False)

    response = db_client.get("/", params={"q": "война"})

    assert "закрыта" in response.text
