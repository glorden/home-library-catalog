# Архитектура

Технический дизайн проекта. Обновляется по мере реализации шагов — то, что
ниже помечено как "шаг N", ещё не реализовано на момент написания раздела,
пока чекбокс в статусе не отмечен.

## Статус

- [x] Шаг 1 — каркас репозитория, Docker, CI
- [ ] Шаг 2 — модель данных и CRUD (код написан: модели, роуты, шаблоны,
      Alembic-обвязка; структура схемы проверена через `SQLModel.metadata` без
      подключения к БД. Реальная миграция и прогон CRUD против настоящего
      Postgres — после установки Docker/Postgres, миграция ещё не
      сгенерирована)
- [ ] Шаг 3 — фото
- [ ] Шаг 4 — AI-извлечение
- [ ] Шаг 5 — аутентификация и витрина
- [ ] Шаг 6 — поиск и дедупликация
- [ ] Шаг 7 — PWA
- [ ] Шаг 8 — деплой на VPS

## Структура репозитория

```
home-library-catalog/
├── .github/{workflows/ci.yml, ISSUE_TEMPLATE/, dependabot.yml, pull_request_template.md}
├── app/
│   ├── main.py, config.py, database.py*, dependencies.py*, security.py*, cli.py*
│   ├── models/*          # editions.py, copies.py, photos.py, user.py,
│   │                      # provider_credential.py + __init__.py со ВСЕМИ импортами
│   ├── schemas/extraction.py*
│   ├── routers/
│   │   ├── pages.py, search.py*, auth.py*                     # публичные
│   │   └── admin_editions.py*, admin_copies.py*, admin_photos.py*,
│   │       admin_settings.py*, extraction.py*                 # APIRouter(prefix="/admin/...",
│   │                                                           #   dependencies=[Depends(require_owner)])
│   ├── services/*
│   │   ├── extraction/{base.py, claude_provider.py, openai_compatible_provider.py,
│   │   │                gemini_provider.py, registry.py}
│   │   ├── photo_storage.py, dedup.py, search.py
│   ├── templates/{base.html, partials/, pages/, admin/*}
│   └── static/{css/input.css, css/output.css (сгенерирован), js/htmx.min.js (скачан),
│                icons/*, manifest.json*, sw.js*}
├── alembic/*  {env.py, versions/}
├── tests/{conftest.py, test_*.py}
├── docker/app/Dockerfile, docker/nginx/*  (nginx — шаг 8)
├── docker-compose.yml, docker-compose.prod.yml*
├── pyproject.toml, Makefile
└── LICENSE, README.md, ARCHITECTURE.md, DEPLOY.md, PROCESS.md
```
`*` — появится на указанном шаге, ещё не создано.

## Ключевые решения

- **Tailwind CSS** собирается standalone CLI-бинарником: `make css` (локально)
  или сборка Docker-образа скачивают бинарник сами. Node.js/npm в репозитории
  нет. `app/static/css/output.css` — сгенерированный файл, в git не хранится.
- **`htmx.min.js`** — не грузится с CDN во время работы сайта: `make vendor`
  или сборка Docker-образа скачивают конкретную зафиксированную версию один
  раз в `app/static/js/`. Файл гитигнорится как build-артефакт (не
  коммитится), но и не тянется с CDN при каждом открытии страницы.
- Публичные и защищённые роуты будут разделены на уровне `APIRouter`
  (`dependencies=[Depends(require_owner)]` на весь роутер, не на отдельные
  функции) — см. "Аутентификация" (шаг 5).
- `app/models/__init__.py` должен импортировать все модели — иначе Alembic
  autogenerate молча не увидит новую таблицу (актуально с шага 2).
- Только `app/services/extraction/*_provider.py` смогут импортировать SDK
  конкретных AI-провайдеров (anthropic/openai/google) — остальной код будет
  работать только через `ExtractionService` Protocol (шаг 4).
- Sync SQLAlchemy, не async — при реальной нагрузке (один владелец + случайные
  посетители витрины) async ничего не даёт, только усложняет.
- Без нативных Postgres ENUM — везде `varchar` + Python `enum.Enum` на уровне
  приложения (ENUM-типы болезненно менять миграциями).

## Модель данных (шаги 2, 4, 5, 6)

**`users`** — ровно одна строка, создаётся CLI, регистрации нет:
`id, email, password_hash (Argon2id), last_login_at, created_at/updated_at`.

**`provider_credentials`** — настройки AI-провайдера (в БД, не в `.env`, так
как idea.md хочет выбор провайдера "в настройках"):
`id, user_id, provider (строка: claude|openai|gemini|openai_compatible),
display_name, api_key_encrypted (Fernet), base_url, model_name, is_active`
(+ частичный уникальный индекс: не более одного активного провайдера на
пользователя).

**`editions`** (библиографическая запись), базовые поля — шаг 2:
`id, title, subtitle, authors (свободный текст — см. риски), original_title,
publisher, publication_year (smallint), publication_year_text ("1930-е",
"б.г."), isbn (индекс), language, series, edition_statement,
physical_description, description, created_at, updated_at`.
Отдельной миграцией на шаге 6 добавляются `dedup_fingerprint (индекс)` и
`search_vector (generated tsvector, GIN, 'russian')` — колонки не нужны раньше
самой функциональности поиска/дедупа, поэтому не создаются заранее.

**`copies`** (физический экземпляр), базовые поля — шаг 2:
`id, edition_id (FK, ON DELETE RESTRICT), inventory_code, condition,
acquisition_date, acquisition_source,
acquisition_price (ВСЕГДА приватно, никогда не в публичном выводе),
storage_location (ВСЕГДА приватно), notes (приватно по умолчанию),
public_notes (отдельное поле для явно публичной заметки), has_autograph,
has_ex_libris, created_at, updated_at`.
Отдельной миграцией на шаге 5 добавляется `is_public (default TRUE — opt-out,
решение принято осознанно)` — вместе с auth, поскольку до появления логина
разделять публичное/приватное не от кого.

**`photos`**:
`id, copy_id (FK, ON DELETE CASCADE — файл с диска сервис удаляет сам, каскад
БД этого не делает), kind (cover|title_page|title_verso|spine|autograph|
ex_libris|damage|other), file_path (относительный, случайный компонент в
имени), original_filename, content_type, file_size_bytes, width, height,
sort_order, created_at`.

**Политика хранения фото**: долговременно хранится только `kind='cover'`.
Остальные снимки (титул, оборот титула и т.д.) — вход для AI-извлечения; их
файлы и записи удаляются сразу после подтверждения записи (шаг 4).
Незавершённые черновики (фото загружены, запись не подтверждена) —
кандидаты на периодическую очистку (например, всё старше 48 часов) — простая
задача-уборщик внутри шага 3, не отдельный этап. Отдельная видимость по фото
не нужна (`is_public` остаётся только на `copies`) — раз хранится только
обложка, её видимость полностью определяется видимостью экземпляра.

**Видимость** — на уровне `copies`, не `editions`: у одной книги может быть и
публичный, и приватный (например, с автографом) экземпляр. Издание попадает
в витрину, если есть хотя бы один публичный экземпляр; приватные просто не
показываются, без намёка на существование. На витрине и странице издания
показывается только обложка публичного экземпляра. Env-переключатель
`SHOWCASE_PUBLIC=true|false` — временно закрыть всю витрину целиком (на время
массового ввода данных).

**Дедупликация**: `dedup_fingerprint = normalize(title)|normalize(author)|year`
(NFKC, lowercase, ё→е, без пунктуации) + точное совпадение ISBN + `pg_trgm`
similarity по title как третий сигнал. Кандидаты только предлагаются в форме
подтверждения, автослияния нет.

**Фото и nginx**: если nginx отдаёт `/media/*` напрямую, `is_public` теряет
смысл — решение `X-Accel-Redirect` (FastAPI проверяет права → просит nginx
`internal;`-location отдать файл), детали в [DEPLOY.md](DEPLOY.md) (шаг 8).

## `ExtractionService` (шаг 4)

```python
class ExtractionImage(BaseModel):
    kind: Literal["cover", "title_page", "title_verso", "other"]
    content: bytes
    media_type: str = "image/jpeg"

class ExtractedField(BaseModel):
    value: str | int | None
    confidence: float | None = None

class ExtractionResult(BaseModel):
    title: ExtractedField | None = None
    authors: ExtractedField | None = None
    publisher: ExtractedField | None = None
    publication_year: ExtractedField | None = None
    isbn: ExtractedField | None = None
    # ... остальные поля editions
    provider_name: str
    model_name: str
    raw_response: str | None = None   # только для аудита, не для показа
    warnings: list[str] = []

class ExtractionService(Protocol):
    provider_name: str
    def extract(self, images: list[ExtractionImage], *, language_hint: str = "ru") -> ExtractionResult: ...
```

Реально нужно 3 реализации, не 5: `claude_provider.py` (Anthropic),
`gemini_provider.py` (Google) и `openai_compatible_provider.py`, который
параметризуется `base_url` + `model_name` и покрывает OpenAI, большинство
локальных LLM-серверов (Ollama/LM Studio/llama.cpp — обычно дают
OpenAI-совместимый endpoint) и "другие совместимые сервисы" одним кодом.

Предобработка фото (resize до ~2000-3000px, JPEG, обязательная зачистка EXIF)
происходит один раз в `photo_storage.py` до отправки в любой провайдер — не
дублируется в каждой реализации.

Хранение настроек — таблица `provider_credentials`, ключи шифруются
`cryptography.fernet.Fernet` с ключом из `SETTINGS_ENCRYPTION_KEY` (env,
никогда не в БД).

## Аутентификация (шаг 5)

Подписанная session-cookie + одна строка в `users`, без ролей/permissions.

- `app/security.py`: `create_session_cookie` / `verify_session_cookie`
  (itsdangerous, HMAC).
- `app/dependencies.py`: `get_current_user` (может вернуть `None`) и
  `require_owner` (кидает ошибку, если `None`).
- Защищённые роутеры: `APIRouter(prefix="/admin/...",
  dependencies=[Depends(require_owner)])` — забыть защитить один эндпоинт
  становится структурно невозможно.
- **htmx-нюанс**: обычный редирект на `/login` в ответ на htmx-запрос
  воткнётся как фрагмент внутрь страницы — сломанный UX. Нужен обработчик,
  отвечающий заголовком `HX-Redirect: /login` при `HX-Request: true` вместо
  обычного `RedirectResponse`. Проверить точное поведение по актуальной
  документации htmx на этом шаге, не полагаться на память.
- Пароль — Argon2id (`argon2-cffi`).
- Bootstrap единственного аккаунта — Typer CLI: `create-admin`,
  `reset-admin-password` (восстановление без email-инфраструктуры).
- CSRF: на MVP достаточно `SameSite=Lax` + `Secure` + `HttpOnly`; явный
  CSRF-токен — post-MVP усиление.
- Rate limiting `/login` — на уровне nginx (`limit_req_zone`), без
  дополнительных Python-зависимостей.

## PWA (шаг 7)

Не offline-first (данные должны быть свежими), а устанавливаемая оболочка:

- `manifest.json` (иконки 192/512 + maskable) + `apple-touch-icon`/мета-теги
  в `base.html` (iOS не полностью следует manifest, нужен отдельный тег).
- `sw.js`: cache-first только для статики (CSS/JS/иконки), network-first с
  fallback на `/offline.html` для навигаций. **Критично**: перехватывать
  только `event.request.mode === 'navigate'` — иначе SW сломает
  htmx-фрагменты, подставляя `/offline.html` внутрь partial-ответа.
  Версионировать `CACHE_NAME`, чистить старые кэши при `activate`.
- Камера: `<input type="file" accept="image/*" capture="environment">` для
  обложки/титула/оборота на форме добавления (уже используется с шага 3, PWA
  на шаге 7 только добавляет манифест/установку/офлайн-заглушку).
- HEIC с айфонов — `pillow-heif` на сервере. Ресайз/EXIF-strip только
  серверный, клиентский JS для этого не нужен.
- HTTPS обязателен для service worker вне localhost — полноценная проверка
  возможна только после деплоя (шаг 8); базовое поведение SW тестируется на
  localhost раньше.

## Риски

1. Порог похожести для дедупа потребует подстройки на реальных данных;
   отдельно проверить дореформенную орфографию (ѣ, і, ѳ, ъ), если такие книги
   есть — нормализация не должна на них падать.
2. AI-стоимость/лимиты — логировать вызовы (провайдер, время, токены), 429 →
   retryable-ошибка, а не падение.
3. Место под фото — умеренный риск (не критичный): долговременно хранится
   только обложка на экземпляр. Но обложки всё равно невосстановимы в
   отличие от БД — бэкап вне VPS с самого начала (см. DEPLOY.md); плюс не
   забыть про очистку незавершённых черновиков, чтобы служебные снимки не
   копились на диске.
4. Service worker и htmx: перехват только navigation-запросов (см. PWA выше)
   — иначе SW сломает htmx-фрагменты.
5. Единственный админ-пароль без email-восстановления — CLI
   `reset-admin-password` протестировать заранее, а не только спроектировать.
6. **Публичная витрина — риск физической безопасности**, не только
   настройка приватности (публичный список ценных вещей, привязанный к
   личности): всегда зачищать EXIF/GPS на сервере у любого фото;
   `acquisition_price`/`storage_location` — всегда приватны независимо от
   `is_public`.
7. Разные AI-провайдеры по-разному справляются с кириллицей/старой
   типографикой/почерком — промпт потребует доработки под каждого, это не
   разовая задача.
8. Не все "OpenAI-совместимые" локальные серверы поддерживают картинки в
   запросах — нужна понятная ошибка пользователю, а не падение.
9. `authors` как свободный текст в MVP ослабит будущий поиск "по автору" —
   осознанное упрощение, вынесено в post-MVP (нормализация в отдельную
   таблицу).
