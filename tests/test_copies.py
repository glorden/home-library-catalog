from sqlmodel import select

from app.models import Copy


def _create_edition(db_client, title: str = "Издание для экземпляров") -> str:
    response = db_client.post("/admin/editions", data={"title": title}, follow_redirects=False)
    return response.headers["location"].rsplit("/", 1)[-1]


def test_create_copy_appears_on_edition_page(db_client):
    edition_id = _create_edition(db_client)

    response = db_client.post(
        f"/admin/editions/{edition_id}/copies",
        data={"inventory_code": "INV-001", "condition": "good"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail_response = db_client.get(f"/admin/editions/{edition_id}")
    assert "INV-001" in detail_response.text


def test_acquisition_price_and_storage_never_in_public_page_html(db_client):
    edition_id = _create_edition(db_client)
    db_client.post(
        f"/admin/editions/{edition_id}/copies",
        data={
            "inventory_code": "INV-002",
            "acquisition_price": "12345.67",
            "storage_location": "Секретный шкаф",
        },
        follow_redirects=False,
    )

    detail_response = db_client.get(f"/admin/editions/{edition_id}")
    assert "12345.67" not in detail_response.text
    assert "Секретный шкаф" not in detail_response.text


def test_edit_form_does_not_render_none_for_empty_fields(db_client):
    edition_id = _create_edition(db_client)
    create_response = db_client.post(
        f"/admin/editions/{edition_id}/copies",
        data={"inventory_code": "MINIMAL"},
        follow_redirects=False,
    )
    copy_id = create_response.headers["location"].rsplit("/", 1)[-1]

    edit_response = db_client.get(f"/admin/copies/{copy_id}/edit")
    assert "None" not in edit_response.text


def test_delete_copy(db_client, session):
    edition_id = _create_edition(db_client)
    create_response = db_client.post(
        f"/admin/editions/{edition_id}/copies",
        data={"inventory_code": "TO-DELETE"},
        follow_redirects=False,
    )
    assert create_response.status_code == 303

    copy = session.exec(select(Copy).where(Copy.edition_id == int(edition_id))).one()

    delete_response = db_client.delete(f"/admin/copies/{copy.id}")
    assert delete_response.status_code == 200

    detail_response = db_client.get(f"/admin/editions/{edition_id}")
    assert "TO-DELETE" not in detail_response.text
