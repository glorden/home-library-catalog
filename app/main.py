import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import admin_copies, admin_editions, admin_settings, extraction, media, pages
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


def create_app() -> FastAPI:
    fastapi_app = FastAPI(title="Каталог домашней библиотеки", lifespan=lifespan)
    fastapi_app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    fastapi_app.include_router(pages.router)
    fastapi_app.include_router(admin_editions.router)
    fastapi_app.include_router(admin_copies.router)
    fastapi_app.include_router(media.router)
    fastapi_app.include_router(extraction.router)
    fastapi_app.include_router(admin_settings.router)

    @fastapi_app.middleware("http")
    async def revalidate_static_assets(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            # Без Cache-Control браузеры кэшируют output.css/htmx.min.js
            # эвристически и не подхватывают правки после пересборки/деплоя.
            response.headers["Cache-Control"] = "no-cache"
        return response

    return fastapi_app


app = create_app()
