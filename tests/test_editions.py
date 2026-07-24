def test_create_edition_then_appears_in_list(db_client):
    response = db_client.post(
        "/admin/editions",
        data={
            "title": "Мастер и Маргарита",
            "authors": "Булгаков М. А.",
            "publication_year": "1967",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    list_response = db_client.get("/admin/editions")
    assert list_response.status_code == 200
    assert "Мастер и Маргарита" in list_response.text
    assert "Булгаков М. А." in list_response.text


def test_edit_edition_updates_fields(db_client):
    create_response = db_client.post(
        "/admin/editions", data={"title": "Исходное название"}, follow_redirects=False
    )
    edition_id = create_response.headers["location"].rsplit("/", 1)[-1]

    update_response = db_client.post(
        f"/admin/editions/{edition_id}",
        data={"title": "Новое название"},
        follow_redirects=False,
    )
    assert update_response.status_code == 303

    detail_response = db_client.get(f"/admin/editions/{edition_id}")
    assert "Новое название" in detail_response.text
    assert "Исходное название" not in detail_response.text


def test_delete_edition_without_copies(db_client):
    create_response = db_client.post(
        "/admin/editions", data={"title": "Удалить меня"}, follow_redirects=False
    )
    edition_id = create_response.headers["location"].rsplit("/", 1)[-1]

    delete_response = db_client.delete(f"/admin/editions/{edition_id}")
    assert delete_response.status_code == 200

    detail_response = db_client.get(f"/admin/editions/{edition_id}")
    assert detail_response.status_code == 404


def test_delete_edition_with_copies_is_blocked(db_client):
    create_response = db_client.post(
        "/admin/editions", data={"title": "С экземпляром"}, follow_redirects=False
    )
    edition_id = create_response.headers["location"].rsplit("/", 1)[-1]
    db_client.post(f"/admin/editions/{edition_id}/copies", data={}, follow_redirects=False)

    delete_response = db_client.delete(f"/admin/editions/{edition_id}")
    assert delete_response.status_code == 409
