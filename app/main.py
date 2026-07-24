from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import pages

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    fastapi_app = FastAPI(title="Каталог домашней библиотеки")
    fastapi_app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    fastapi_app.include_router(pages.router)
    return fastapi_app


app = create_app()
