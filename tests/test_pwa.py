import math
from pathlib import Path

from PIL import Image

ICONS_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"


def test_manifest_served(client):
    response = client.get("/static/manifest.json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    manifest = response.json()
    assert manifest["name"]
    assert len(manifest["short_name"]) <= 12
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"
    assert len(manifest["icons"]) == 3


def test_manifest_icons_are_served(client):
    manifest = client.get("/static/manifest.json").json()
    for icon in manifest["icons"]:
        response = client.get(icon["src"])
        assert response.status_code == 200, icon["src"]
        assert response.headers["content-type"] == "image/png"


def test_manifest_has_both_any_and_maskable_icons(client):
    manifest = client.get("/static/manifest.json").json()
    purposes = {icon.get("purpose") for icon in manifest["icons"]}
    assert purposes == {"any", "maskable"}


def test_service_worker_served_at_root_scope(client):
    # Корневой путь, а не /static/sw.js — иначе scope SW не покрыл бы
    # навигации на "/", "/catalog/*" и т.д. (см. ARCHITECTURE.md, шаг 7).
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"
    body = response.text
    assert "CACHE_NAME" in body
    # Риск №4: перехватывать только навигации, иначе SW подменит
    # офлайн-страницей htmx-фрагменты.
    assert 'request.mode === "navigate"' in body


def test_offline_page_renders(client):
    response = client.get("/offline.html")
    assert response.status_code == 200
    assert "Нет соединения" in response.text


def test_home_page_includes_manifest_and_sw_registration(db_client):
    response = db_client.get("/")
    assert response.status_code == 200
    assert 'rel="manifest"' in response.text
    assert 'serviceWorker.register("/sw.js")' in response.text


def test_favicon_contains_all_expected_sizes():
    favicon = Image.open(ICONS_DIR / "favicon.ico")
    assert favicon.info["sizes"] == {(16, 16), (32, 32), (48, 48)}


def test_maskable_icon_glyph_stays_inside_safe_zone():
    # Спецификация maskable icons: контент должен уместиться во вписанную
    # окружность радиусом 40% стороны иконки — иначе Android обрежет глиф
    # при наложении своей маски формы.
    icon = Image.open(ICONS_DIR / "icon-maskable-512.png").convert("RGBA")
    width, height = icon.size
    center_x, center_y = width / 2, height / 2
    safe_radius = 0.4 * width
    pixels = icon.load()
    background = pixels[0, 0]

    max_glyph_radius = max(
        math.hypot(x - center_x, y - center_y)
        for y in range(height)
        for x in range(width)
        if pixels[x, y] != background
    )

    assert max_glyph_radius <= safe_radius
