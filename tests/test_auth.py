import pytest
import typer
from sqlmodel import select

from app import cli, security
from app.models import User

EMAIL = "owner@example.com"
PASSWORD = "correct horse battery staple"


def _create_user(session, email=EMAIL, password=PASSWORD) -> User:
    user = User(email=email, password_hash=security.hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_login_success_sets_cookie_and_redirects(auth_client, session):
    _create_user(session)

    response = auth_client.post(
        "/login", data={"email": EMAIL, "password": PASSWORD}, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/editions"
    assert security.SESSION_COOKIE_NAME in response.cookies

    protected = auth_client.get("/admin/editions")
    assert protected.status_code == 200


def test_login_wrong_password_shows_generic_error(auth_client, session):
    _create_user(session)

    response = auth_client.post(
        "/login", data={"email": EMAIL, "password": "неверный пароль"}, follow_redirects=False
    )

    assert response.status_code == 401
    assert "Неверный email или пароль" in response.text
    assert security.SESSION_COOKIE_NAME not in response.cookies


def test_login_unknown_email_shows_same_generic_error(auth_client, session):
    response = auth_client.post(
        "/login",
        data={"email": "nobody@example.com", "password": PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "Неверный email или пароль" in response.text


def test_protected_route_without_cookie_redirects_to_login(auth_client):
    response = auth_client.get("/admin/editions", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_protected_route_htmx_without_cookie_gets_hx_redirect(auth_client):
    """HX-Redirect не обрабатывается htmx на 3xx-ответах — обработчик обязан
    вернуть 200 на htmx-запросах, иначе hx-delete на "протухшей" сессии
    воткнёт битый фрагмент вместо навигации на /login."""
    response = auth_client.get(
        "/admin/editions", headers={"HX-Request": "true"}, follow_redirects=False
    )

    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == "/login"


def test_logout_clears_cookie(auth_client, session):
    _create_user(session)
    auth_client.post("/login", data={"email": EMAIL, "password": PASSWORD}, follow_redirects=False)
    assert auth_client.get("/admin/editions").status_code == 200

    auth_client.post("/logout", follow_redirects=False)

    response = auth_client.get("/admin/editions", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_cli_create_admin_then_refuses_second(session, monkeypatch):
    monkeypatch.setattr(cli, "engine", session.get_bind())
    monkeypatch.setattr(cli.typer, "prompt", lambda *args, **kwargs: PASSWORD)

    cli.create_admin(email=EMAIL)

    user = session.exec(select(User).where(User.email == EMAIL)).first()
    assert user is not None
    assert security.verify_password(PASSWORD, user.password_hash)

    with pytest.raises(typer.Exit):
        cli.create_admin(email="another@example.com")


def test_cli_reset_admin_password_invalidates_old_cookie(session, monkeypatch):
    monkeypatch.setattr(cli, "engine", session.get_bind())
    user = _create_user(session)
    old_token = security.create_session_cookie(user)

    monkeypatch.setattr(cli.typer, "prompt", lambda *args, **kwargs: "новый пароль надёжный")
    cli.reset_admin_password()

    session.refresh(user)
    assert security.verify_session_cookie(old_token, session) is None
    assert security.verify_password("новый пароль надёжный", user.password_hash)
