def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Каталог домашней библиотеки" in response.text


def test_greeting_partial(client):
    response = client.get("/partials/greeting")
    assert response.status_code == 200
    assert "htmx" in response.text
