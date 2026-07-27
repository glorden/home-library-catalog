import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.config import settings
from app.database import engine
from app.dependencies import NotAuthenticatedError, load_current_user_for_request
from app.routers import (
    admin_copies,
    admin_editions,
    admin_settings,
    auth,
    extraction,
    media,
    pages,
)
from app.services import photo_storage

BASE_DIR = Path(__file__).resolve().parent

DRAFT_CLEANUP_INTERVAL_SECONDS = 6 * 3600


async def _draft_cleanup_loop() -> None:
    while True:
        await asyncio.to_thread(photo_storage.sweep_abandoned_drafts)
        await asyncio.sleep(DRAFT_CLEANUP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    task = None
    if settings.enable_draft_cleanup_loop:
        task = asyncio.create_task(_draft_cleanup_loop())
    yield
    if task is not None:
        task.cancel()


def _configure_logging() -> None:
    # Без хендлера logger.info(...) в app/services/extraction/*_provider.py
    # никуда не попадают: запись доходит до root без обработчиков и
    # отбрасывается lastResort'ом (у него самого уровень WARNING) — проверено
    # вживую на проде во время реальных вызовов, см. ARCHITECTURE.md, шаг 9.
    # Настраиваем только неймспейс "app" (не root), чтобы не потащить
    # DEBUG/INFO-шум сторонних библиотек (httpx, openai и т.п.) — их уровень
    # не меняется.
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(handler)


def create_app() -> FastAPI:
    _configure_logging()
    fastapi_app = FastAPI(title="Каталог домашней библиотеки", lifespan=lifespan)
    fastapi_app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    fastapi_app.include_router(pages.router)
    fastapi_app.include_router(auth.router)
    fastapi_app.include_router(admin_editions.router)
    fastapi_app.include_router(admin_copies.router)
    fastapi_app.include_router(media.router)
    fastapi_app.include_router(extraction.router)
    fastapi_app.include_router(admin_settings.router)

    @fastapi_app.middleware("http")
    async def load_current_user(request: Request, call_next):
        request.state.user = None
        if not request.url.path.startswith("/static/"):
            with Session(engine) as session:
                request.state.user = load_current_user_for_request(request, session)
        return await call_next(request)

    @fastapi_app.middleware("http")
    async def revalidate_static_assets(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            # Без Cache-Control браузеры кэшируют output.css/htmx.min.js
            # эвристически и не подхватывают правки после пересборки/деплоя.
            response.headers["Cache-Control"] = "no-cache"
        return response

    @fastapi_app.exception_handler(NotAuthenticatedError)
    async def handle_not_authenticated(request: Request, exc: NotAuthenticatedError):
        # HX-Redirect не обрабатывается htmx на 3xx-ответах (см. ARCHITECTURE.md,
        # шаг 5) — на htmx-запросах обязателен 200, иначе кнопки вроде
        # hx-delete на "протухшей" сессии просто воткнут фрагмент в DOM.
        if request.headers.get("HX-Request") == "true":
            return Response(status_code=200, headers={"HX-Redirect": "/login"})
        return RedirectResponse("/login", status_code=303)

    return fastapi_app


app = create_app()
