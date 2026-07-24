from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import admin_copies, admin_editions, pages

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    fastapi_app = FastAPI(title="Каталог домашней библиотеки")
    fastapi_app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    fastapi_app.include_router(pages.router)
    fastapi_app.include_router(admin_editions.router)
    fastapi_app.include_router(admin_copies.router)
    return fastapi_app


app = create_app()
