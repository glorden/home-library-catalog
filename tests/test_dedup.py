from app.models import Edition
from app.services.dedup import (
    apply_fingerprint,
    compute_fingerprint,
    find_candidates,
    normalize_text,
)


def test_normalize_text_survives_pre_reform_orthography():
    # ѣ, і, ѳ, ъ — риск №1 из ARCHITECTURE.md: нормализация не должна на них
    # падать и не должна их выедать как "не буквы" (буквы проверены через
    # unicodedata.name() — не полагаемся на визуальное сходство с латиницей).
    result = normalize_text("Мір, Фѣдоръ и рѣка.")
    assert result == "мір фѣдоръ и рѣка"
    assert "," not in result
    assert "." not in result


def test_normalize_text_preserves_fita_and_yat_letters():
    result = normalize_text("Ѳедоръ и рѣка")
    assert "ѳедор" in result
    assert "рѣка" in result


def test_normalize_text_folds_yo_to_ye():
    assert normalize_text("Ёжик в тумане") == normalize_text("Ежик в тумане")
    assert "ё" not in normalize_text("Ёлка")


def test_normalize_text_strips_punctuation_and_collapses_whitespace():
    assert normalize_text("  Война,   и   мир!  ") == "война и мир"


def test_compute_fingerprint_ignores_punctuation_and_case():
    a = compute_fingerprint("Война и мир", "Толстой Л. Н.", 1869)
    b = compute_fingerprint("война, и мир.", "толстой л.н.", 1869)
    assert a == b


def test_compute_fingerprint_differs_on_year():
    a = compute_fingerprint("Война и мир", "Толстой", 1869)
    b = compute_fingerprint("Война и мир", "Толстой", 1873)
    assert a != b


def test_compute_fingerprint_handles_missing_authors_and_year():
    # не должно падать на None; год отсутствует — не "0", а пустая часть
    fp = compute_fingerprint("Название без автора и года", None, None)
    assert fp == "название без автора и года||"


def test_apply_fingerprint_sets_field_on_instance():
    edition = Edition(title="Мастер и Маргарита", authors="Булгаков М. А.", publication_year=1967)
    assert edition.dedup_fingerprint is None
    apply_fingerprint(edition)
    assert edition.dedup_fingerprint == compute_fingerprint(
        "Мастер и Маргарита", "Булгаков М. А.", 1967
    )


def test_find_candidates_empty_title_returns_nothing(session):
    assert find_candidates(session, title="", authors=None, year=None, isbn=None) == []
    assert find_candidates(session, title="   ", authors=None, year=None, isbn=None) == []


def _make_edition(session, **kwargs) -> Edition:
    edition = Edition(**kwargs)
    apply_fingerprint(edition)
    session.add(edition)
    session.commit()
    session.refresh(edition)
    return edition


def test_find_candidates_matches_by_isbn_ignoring_hyphenation(session):
    existing = _make_edition(session, title="Совсем другое название", isbn="978-5-699-10138-8")

    candidates = find_candidates(
        session, title="Новый черновик", authors=None, year=None, isbn="9785699101388"
    )

    assert len(candidates) == 1
    assert candidates[0].edition.id == existing.id
    assert candidates[0].reason == "isbn"


def test_find_candidates_matches_by_fingerprint(session):
    existing = _make_edition(
        session, title="Мастер и Маргарита", authors="Булгаков М. А.", publication_year=1967
    )

    candidates = find_candidates(
        session,
        title="мастер и маргарита",
        authors="булгаков м. а.",
        year=1967,
        isbn=None,
    )

    assert len(candidates) == 1
    assert candidates[0].edition.id == existing.id
    assert candidates[0].reason == "fingerprint"


def test_find_candidates_matches_by_title_similarity(session):
    existing = _make_edition(session, title="Мастер и Маргарита", publication_year=1967)

    # Похожее, но не идентичное название/год — fingerprint не совпадёт,
    # должен сработать именно триграммный сигнал.
    candidates = find_candidates(
        session, title="Мастер и Маргарита (роман)", authors=None, year=1973, isbn=None
    )

    assert len(candidates) == 1
    assert candidates[0].edition.id == existing.id
    assert candidates[0].reason == "title_similarity"


def test_find_candidates_excludes_self_when_editing(session):
    existing = _make_edition(
        session, title="Мастер и Маргарита", authors="Булгаков М. А.", publication_year=1967
    )

    candidates = find_candidates(
        session,
        title="Мастер и Маргарита",
        authors="Булгаков М. А.",
        year=1967,
        isbn=None,
        exclude_edition_id=existing.id,
    )

    assert candidates == []


def test_find_candidates_no_match_for_unrelated_title(session):
    _make_edition(session, title="Мастер и Маргарита", publication_year=1967)

    candidates = find_candidates(
        session, title="Совершенно другая книга про космос", authors=None, year=None, isbn=None
    )

    assert candidates == []


# --- Интеграционные тесты через HTTP: dedup_fingerprint проставляется при
# создании/редактировании издания, эндпоинт dedup-candidates отвечает
# ожидаемым HTML-фрагментом. ---


def test_create_edition_via_form_sets_dedup_fingerprint(db_client, session):
    response = db_client.post(
        "/admin/editions",
        data={
            "title": "Мастер и Маргарита",
            "authors": "Булгаков М. А.",
            "publication_year": "1967",
        },
        follow_redirects=False,
    )
    edition_id = int(response.headers["location"].rsplit("/", 1)[-1])

    edition = session.get(Edition, edition_id)
    assert edition.dedup_fingerprint == compute_fingerprint(
        "Мастер и Маргарита", "Булгаков М. А.", 1967
    )


def test_update_edition_recomputes_dedup_fingerprint(db_client, session):
    create_response = db_client.post(
        "/admin/editions", data={"title": "Исходное название"}, follow_redirects=False
    )
    edition_id = int(create_response.headers["location"].rsplit("/", 1)[-1])

    db_client.post(
        f"/admin/editions/{edition_id}",
        data={"title": "Новое название", "authors": "Новый автор"},
        follow_redirects=False,
    )

    edition = session.get(Edition, edition_id)
    assert edition.dedup_fingerprint == compute_fingerprint("Новое название", "Новый автор", None)


def test_dedup_candidates_endpoint_finds_similar_edition(db_client):
    create_response = db_client.post(
        "/admin/editions",
        data={
            "title": "Мастер и Маргарита",
            "authors": "Булгаков М. А.",
            "publication_year": "1967",
        },
        follow_redirects=False,
    )
    edition_id = create_response.headers["location"].rsplit("/", 1)[-1]

    response = db_client.get(
        "/admin/editions/dedup-candidates",
        params={
            "title": "мастер и маргарита",
            "authors": "булгаков м. а.",
            "publication_year": "1967",
        },
    )

    assert response.status_code == 200
    assert "Мастер и Маргарита" in response.text
    assert f"/admin/editions/{edition_id}" in response.text
    assert "похоже, то же издание" in response.text


def test_dedup_candidates_endpoint_excludes_self(db_client):
    create_response = db_client.post(
        "/admin/editions",
        data={
            "title": "Мастер и Маргарита",
            "authors": "Булгаков М. А.",
            "publication_year": "1967",
        },
        follow_redirects=False,
    )
    edition_id = create_response.headers["location"].rsplit("/", 1)[-1]

    response = db_client.get(
        "/admin/editions/dedup-candidates",
        params={
            "title": "Мастер и Маргарита",
            "authors": "Булгаков М. А.",
            "publication_year": "1967",
            "exclude_edition_id": edition_id,
        },
    )

    assert response.status_code == 200
    assert "Мастер и Маргарита" not in response.text


def test_dedup_candidates_endpoint_empty_title_returns_no_warning(db_client):
    response = db_client.get("/admin/editions/dedup-candidates", params={"title": ""})

    assert response.status_code == 200
    assert "Похоже" not in response.text


def test_dedup_candidates_endpoint_tolerates_garbage_year_without_422(db_client):
    response = db_client.get(
        "/admin/editions/dedup-candidates",
        params={"title": "Что угодно", "publication_year": "not-a-number"},
    )

    assert response.status_code == 200
