def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_page_renders(db_client):
    response = db_client.get("/")
    assert response.status_code == 200
    assert "Каталог домашней библиотеки" in response.text
