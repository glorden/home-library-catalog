"""Генерирует иконки PWA локально через Pillow — без сторонних сервисов
генерации favicon/манифеста (см. ARCHITECTURE.md, шаг 7).

Запуск: python scripts/generate_pwa_icons.py
Результат — app/static/icons/*.png, favicon.ico. Детерминированно:
перезапуск с тем же кодом даёт побитово одинаковый результат.
"""

from pathlib import Path

from PIL import Image, ImageDraw

BG_COLOR = (79, 70, 229, 255)  # indigo-600 (#4f46e5) — акцентный цвет проекта
GLYPH_COLOR = (255, 255, 255, 255)
SUPERSAMPLE = 4  # рисуем в 4x и уменьшаем LANCZOS'ом — сглаживание без AA-примитивов PIL

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"

# Силуэт раскрытой книги: две "страницы"-трапеции с зазором-корешком по
# центру. Координаты — доли стороны глиф-бокса (0..1), левая страница;
# правая получается зеркалированием по x=0.5.
LEFT_PAGE = [
    (0.10, 0.14),
    (0.47, 0.20),
    (0.47, 0.82),
    (0.06, 0.72),
]

# "any" — обычный отступ, углы при необходимости скруглит сама ОС/браузер.
MARGIN_STANDARD = 0.18
# "maskable" — глиф должен уместиться в безопасную зону (вписанный круг
# радиусом 40% стороны иконки), берём заметно больший отступ с запасом.
MARGIN_MASKABLE = 0.24
# favicon — крупнее отступ не нужен, глиф должен быть виден и на 16px.
MARGIN_FAVICON = 0.14


def _mirror(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(1 - u, v) for u, v in points]


def _book_icon(size: int, margin_fraction: float) -> Image.Image:
    hi_res = size * SUPERSAMPLE
    img = Image.new("RGBA", (hi_res, hi_res), BG_COLOR)
    draw = ImageDraw.Draw(img)

    glyph_size = hi_res * (1 - 2 * margin_fraction)
    offset = (hi_res - glyph_size) / 2

    def to_px(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [(offset + u * glyph_size, offset + v * glyph_size) for u, v in points]

    draw.polygon(to_px(LEFT_PAGE), fill=GLYPH_COLOR)
    draw.polygon(to_px(_mirror(LEFT_PAGE)), fill=GLYPH_COLOR)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    _book_icon(192, MARGIN_STANDARD).save(OUTPUT_DIR / "icon-192.png")
    _book_icon(512, MARGIN_STANDARD).save(OUTPUT_DIR / "icon-512.png")
    _book_icon(512, MARGIN_MASKABLE).save(OUTPUT_DIR / "icon-maskable-512.png")

    # iOS сама накладывает маску/скругление на apple-touch-icon — отдаём
    # непрозрачный квадрат без ручного скругления углов.
    _book_icon(180, MARGIN_STANDARD).convert("RGB").save(OUTPUT_DIR / "apple-touch-icon.png")

    favicon_source = _book_icon(48, MARGIN_FAVICON)
    favicon_source.save(OUTPUT_DIR / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

    print(f"Иконки сгенерированы в {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
