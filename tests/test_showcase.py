from sqlmodel import select

from app.config import settings
from app.models import Copy


def _create_edition(db_client, title: str) -> int:
    response = db_client.post("/admin/editions", data={"title": title}, follow_redirects=False)
    return int(response.headers["location"].rsplit("/", 1)[-1])


def test_home_lists_only_editions_with_public_copies(db_client, session):
    public_id = _create_edition(db_client, "Публичная книга")
    # Как настоящий чекбокс в браузере: не отправлен — не публичен. Тестовый
    # POST не рендерит форму (которая по умолчанию отправляет is_public=true
    # для нового экземпляра), поэтому здесь нужно указать явно.
    db_client.post(
        f"/admin/editions/{public_id}/copies",
        data={"is_public": "true"},
        follow_redirects=False,
    )

    private_id = _create_edition(db_client, "Приватная книга")
    db_client.post(f"/admin/editions/{private_id}/copies", data={}, follow_redirects=False)
    private_copy = session.exec(select(Copy).where(Copy.edition_id == private_id)).one()
    private_copy.is_public = False
    session.add(private_copy)
    session.commit()

    response = db_client.get("/")

    assert "Публичная книга" in response.text
    assert "Приватная книга" not in response.text


def test_catalog_detail_404s_when_no_public_copies(db_client, session):
    edition_id = _create_edition(db_client, "Только приватный экземпляр")
    db_client.post(f"/admin/editions/{edition_id}/copies", data={}, follow_redirects=False)
    copy = session.exec(select(Copy).where(Copy.edition_id == edition_id)).one()
    copy.is_public = False
    session.add(copy)
    session.commit()

    response = db_client.get(f"/catalog/{edition_id}")
    assert response.status_code == 404


def test_catalog_detail_404s_for_nonexistent_edition(db_client):
    response = db_client.get("/catalog/999999")
    assert response.status_code == 404


def test_showcase_closed_when_disabled(db_client, monkeypatch):
    monkeypatch.setattr(settings, "showcase_public", False)

    response = db_client.get("/")

    assert "закрыта" in response.text
