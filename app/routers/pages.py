from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "pages/home.html", {})


@router.get("/partials/greeting")
def greeting(request: Request):
    return templates.TemplateResponse(request, "partials/greeting.html", {})
