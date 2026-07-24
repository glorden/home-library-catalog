# Каталог домашней библиотеки

Open-source каталог домашней библиотеки с упором на быструю каталогизацию
бумажных книг — особенно советских и старых изданий без ISBN.

Основной сценарий: сфотографировать обложку, титульный лист и оборот титула →
получить структурированные библиографические данные через выбранный
AI-сервис → проверить и подтвердить → сохранить. AI никогда не пишет в базу
без подтверждения пользователя.

Подробнее об идее — в [idea.md](idea.md).

## Стек

- Backend: FastAPI
- База данных: PostgreSQL + SQLModel + Alembic
- Frontend: Jinja2 + htmx + Tailwind CSS (без React, без Node/npm)
- Инфраструктура: Docker Compose, nginx, Certbot
- Мобильный доступ: PWA (тот же веб, устанавливаемый на телефон)

Технические детали — в [ARCHITECTURE.md](ARCHITECTURE.md).
Деплой на VPS — в [DEPLOY.md](DEPLOY.md).
Процесс разработки (ветки, CI, лейблы) — в [PROCESS.md](PROCESS.md).

## Быстрый старт (разработка)

Через Docker (рекомендуется — сам скачивает Tailwind CLI и htmx.min.js при
сборке образа):

```bash
docker compose up --build
```

Приложение будет доступно на http://localhost:8000, проверка здоровья — на
`/healthz`.

Без Docker (venv):

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Без Docker страница откроется без стилей и без htmx, пока не собраны
статические файлы:

```bash
make vendor   # скачивает htmx.min.js
make css      # скачивает standalone Tailwind CLI и собирает output.css
```

Оба таргета качают файлы из интернета (unpkg.com / GitHub releases) — сначала
проверьте содержимое `Makefile`, если это важно для вашего окружения.

## Тесты и линт

```bash
pytest
ruff check app tests
ruff format --check app tests
```
