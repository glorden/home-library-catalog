# Home Library Catalog

*English | [Русский](README.md) (основная версия)*

An open-source home library catalog focused on fast cataloging of paper
books — especially Soviet-era and old editions without an ISBN.

Main flow: photograph the cover (the title page and its verso are optional,
for better recognition accuracy) → get structured bibliographic data back
from your chosen AI service → review and confirm → save. AI never writes to
the database without user confirmation.

More on the idea — in [idea.md](idea.md) (in Russian).

## Stack

- Backend: FastAPI
- Database: PostgreSQL + SQLModel + Alembic
- Frontend: Jinja2 + htmx + Tailwind CSS (no React, no Node/npm)
- Infrastructure: Docker Compose, Caddy
- Mobile access: PWA (the same web app, installable on a phone)

Technical details — in [ARCHITECTURE.md](ARCHITECTURE.md) (in Russian).
VPS deployment — in [DEPLOY.md](DEPLOY.md) (in Russian).
Development process (branches, CI, labels) — in [PROCESS.md](PROCESS.md)
(in Russian).
Changelog — in [CHANGELOG.md](CHANGELOG.md).

## Quick start (development)

Via Docker (recommended — downloads the Tailwind CLI and htmx.min.js itself
during the image build):

```bash
docker compose up --build
```

The app will be available at http://localhost:8000, health check at
`/healthz`.

Without Docker (venv):

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Without Docker the page will open without styles and without htmx until the
static assets are built:

```bash
make vendor   # downloads htmx.min.js
make css      # downloads the standalone Tailwind CLI and builds output.css
```

Both targets download files from the internet (unpkg.com / GitHub
releases) — check the `Makefile` contents first if that matters for your
environment.

## Owner login

All `/admin/*` routes and AI recognition require login. There is exactly
one account, no in-app registration — it's created via the CLI. Generate a
session-cookie signing key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put the result into `.env` (repo root, not committed):

```
SESSION_SECRET_KEY=<generated value>
```

Recreate the container (environment variables are only picked up on
creation, not on a plain restart) and create the owner account:

```bash
docker compose up -d
docker compose exec app python -m app.cli create-admin --email you@example.com
```

The password is prompted interactively (input hidden, so it doesn't end up
in shell history). If the password is lost — `docker compose exec app
python -m app.cli reset-admin-password` (also invalidates every
already-issued session cookie). Then go to `/login`.

## AI provider setup

To try photo-based recognition (`/admin/extract/new`), generate an
encryption key and configure a provider:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the result into `.env` (repo root, not committed):

```
SETTINGS_ENCRYPTION_KEY=<generated value>
```

Recreate the container (environment variables are only picked up on
creation, not on a plain restart):

```bash
docker compose up -d
```

Open `/admin/settings` and configure one of the providers:

- **Claude (Anthropic)** — get a key at
  [console.anthropic.com](https://console.anthropic.com);
- **OpenAI-compatible** — works with Groq, Gemini (via its OpenAI-compatible
  endpoint), and local servers like Ollama/LM Studio; needs that service's
  `base_url` (see the hint in the form).

## Tests and lint

```bash
pytest
ruff check app tests scripts
ruff format --check app tests scripts
```
