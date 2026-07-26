from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from app import security
from app.config import settings
from app.dependencies import SessionDep
from app.models.user import User
from app.timeutil import utcnow

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(tags=["auth"])

LOGIN_ERROR = "Неверный email или пароль"


def _set_session_cookie(response: RedirectResponse, user: User) -> None:
    try:
        token = security.create_session_cookie(user)
    except security.SessionSecretNotConfiguredError as exc:
        raise HTTPException(
            status_code=500,
            detail="Сервер не настроен: переменная окружения SESSION_SECRET_KEY не задана",
        ) from exc
    response.set_cookie(
        security.SESSION_COOKIE_NAME,
        token,
        max_age=security.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        path="/",
    )


@router.get("/login")
def login_form(request: Request):
    if request.state.user is not None:
        return RedirectResponse("/admin/editions", status_code=303)
    return templates.TemplateResponse(request, "pages/login.html", {"error": None})


@router.post("/login")
def login(
    request: Request,
    session: SessionDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not security.verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "pages/login.html", {"error": LOGIN_ERROR}, status_code=401
        )

    user.last_login_at = utcnow()
    session.add(user)
    session.commit()

    response = RedirectResponse("/admin/editions", status_code=303)
    _set_session_cookie(response, user)
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(security.SESSION_COOKIE_NAME, path="/")
    return response
