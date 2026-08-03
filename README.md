# Каталог домашней библиотеки

*[English](README.en.md) | Русский (этот файл)*

Open-source каталог домашней библиотеки с упором на быструю каталогизацию
бумажных книг — особенно советских и старых изданий без ISBN.

Основной сценарий: сфотографировать обложку (титульный лист и его оборот —
опционально, для точности) → получить структурированные библиографические
данные через выбранный AI-сервис → проверить и подтвердить → сохранить. AI
никогда не пишет в базу без подтверждения пользователя.

Подробнее об идее — в [idea.md](idea.md).

## Стек

- Backend: FastAPI
- База данных: PostgreSQL + SQLModel + Alembic
- Frontend: Jinja2 + htmx + Tailwind CSS (без React, без Node/npm)
- Инфраструктура: Docker Compose, Caddy
- Мобильный доступ: PWA (тот же веб, устанавливаемый на телефон)

Технические детали — в [ARCHITECTURE.md](ARCHITECTURE.md).
Деплой на VPS — в [DEPLOY.md](DEPLOY.md).
Процесс разработки (ветки, CI, лейблы) — в [PROCESS.md](PROCESS.md).
Журнал изменений — в [CHANGELOG.md](CHANGELOG.md).

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

## Вход владельца

Все `/admin/*`-роуты и AI-распознавание требуют входа. Аккаунт ровно один,
регистрации в приложении нет — создаётся через CLI. Сгенерируйте ключ
подписи session cookie:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Положите результат в `.env` (в корне репозитория, не коммитится):

```
SESSION_SECRET_KEY=<сгенерированное значение>
```

Пересоздайте контейнер (переменные окружения подхватываются только при
создании, не при обычном рестарте) и создайте владельца:

```bash
docker compose up -d
docker compose exec app python -m app.cli create-admin --email you@example.com
```

Пароль спросит интерактивно (ввод скрыт, чтобы не осел в истории шелла).
Если пароль забыт — `docker compose exec app python -m app.cli
reset-admin-password` (сбрасывает и все уже выданные session cookie).
Дальше — `/login`.

## Настройка AI-провайдера

Чтобы попробовать распознавание по фото (`/admin/extract/new`), нужно
сгенерировать ключ шифрования и настроить провайдера:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Положите результат в `.env` (в корне репозитория, не коммитится):

```
SETTINGS_ENCRYPTION_KEY=<сгенерированное значение>
```

Пересоздайте контейнер (переменные окружения подхватываются только при
создании, не при обычном рестарте):

```bash
docker compose up -d
```

Откройте `/admin/settings` и укажите одного из провайдеров:

- **Claude (Anthropic)** — ключ из [console.anthropic.com](https://console.anthropic.com);
- **OpenAI-совместимый** — подходит для Groq, Gemini (через её
  OpenAI-совместимый эндпоинт) и локальных серверов вроде Ollama/LM Studio;
  нужен `base_url` конкретного сервиса (см. подсказку в форме).

## Тесты и линт

```bash
pytest
ruff check app tests scripts
ruff format --check app tests scripts
```
