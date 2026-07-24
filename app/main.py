from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.routers import admin_copies, admin_editions, media, pages

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    fastapi_app = FastAPI(title="Каталог домашней библиотеки")
    fastapi_app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    fastapi_app.include_router(pages.router)
    fastapi_app.include_router(admin_editions.router)
    fastapi_app.include_router(admin_copies.router)
    fastapi_app.include_router(media.router)

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
