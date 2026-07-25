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


def test_original_title_round_trips_through_create_and_edit(db_client):
    create_response = db_client.post(
        "/admin/editions",
        data={"title": "Волхв", "original_title": "The Magus"},
        follow_redirects=False,
    )
    edition_id = create_response.headers["location"].rsplit("/", 1)[-1]

    edit_response = db_client.get(f"/admin/editions/{edition_id}/edit")
    assert 'value="The Magus"' in edit_response.text

    db_client.post(
        f"/admin/editions/{edition_id}",
        data={"title": "Волхв", "original_title": "The Magus Revised"},
        follow_redirects=False,
    )
    edit_response = db_client.get(f"/admin/editions/{edition_id}/edit")
    assert 'value="The Magus Revised"' in edit_response.text
    assert 'value="The Magus"' not in edit_response.text


def test_edit_form_does_not_render_none_for_empty_fields(db_client):
    create_response = db_client.post(
        "/admin/editions", data={"title": "Минимальное издание"}, follow_redirects=False
    )
    edition_id = create_response.headers["location"].rsplit("/", 1)[-1]

    edit_response = db_client.get(f"/admin/editions/{edition_id}/edit")
    assert "None" not in edit_response.text


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
