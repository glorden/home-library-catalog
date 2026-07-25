# Архитектура

Технический дизайн проекта. Обновляется по мере реализации шагов — то, что
ниже помечено как "шаг N", ещё не реализовано на момент написания раздела,
пока чекбокс в статусе не отмечен.

## Статус

- [x] Шаг 1 — каркас репозитория, Docker, CI
- [x] Шаг 2 — модель данных и CRUD (проверено вживую через `docker compose up`:
      миграция сгенерирована и применена, upgrade/downgrade работают, CRUD
      изданий/экземпляров проверен в браузере, FK RESTRICT/CASCADE
      подтверждены, 10/10 тестов проходят против настоящего Postgres в
      отдельной БД `library_test`)
- [x] Шаг 3 — фото (загрузка/ресайз/EXIF-strip обложки проверены на реальных
      фото с телефона — 2.6 МБ 1920×2560 → 438 КБ 1200×1600, без EXIF;
      замена и удаление обложки корректно чистят файл с диска; 16/16 тестов
      проходят)
- [x] Шаг 4 — AI-извлечение (проверено вживую: `docker compose up --build`,
      миграция `provider_credentials` применена и накатана/откачена в
      контейнере, partial unique index подтверждён реальными INSERT;
      43/43 теста проходят на `FakeExtractionService`, реальный сетевой вызов
      не выполняется в CI. Полный сценарий фото → распознавание →
      подтверждение → сохранение → очистка черновика проверен вживую через
      OpenAI-совместимый провайдер на реальном Gemini-ключе (`gemini-flash-latest`
      через `https://generativelanguage.googleapis.com/v1beta/openai/`) —
      кириллица прошла через форму без искажений. Сам Claude-провайдер живым
      вызовом не проверялся (пользователь тестировал бесплатным Gemini-ключом
      вместо платного Claude) — покрыт только тестами схемы/парсинга;
      структура кода у обоих провайдеров идентична, реальный вызов Claude
      можно проверить в любой момент, когда появится ключ)
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
│   ├── schemas/extraction.py
│   ├── routers/
│   │   ├── pages.py, search.py*, auth.py*                     # публичные
│   │   └── admin_editions.py, admin_copies.py, admin_settings.py,
│   │       extraction.py                                      # APIRouter(prefix="/admin/...",
│   │                                                           #   dependencies=[Depends(require_owner)] — шаг 5)
│   ├── services/*
│   │   ├── extraction/{base.py, claude_provider.py,
│   │   │                openai_compatible_provider.py, registry.py}
│   │   ├── photo_storage.py, crypto.py, dedup.py, search.py
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
- **docker-compose.yml монтирует dev-volume точечно (по файлам/подпапкам
  `app/`), а не всю `./app:/code/app`** — иначе bind mount перекрывает
  `app/static/{css/output.css,js/htmx.min.js}`, собранные ВНУТРИ образа, и
  контейнер тихо показывает протухшую версию CSS/JS с хоста. Наступили на
  это на шаге 3 — новые Tailwind-классы не применялись, пока не нашли
  причину.
- Статика отдаётся с `Cache-Control: no-cache` (middleware в `main.py`) —
  без этого браузер эвристически кэширует `output.css`/`htmx.min.js` и не
  видит правки после пересборки/деплоя, даже если файл на сервере уже новый.
- В формах `edition_form.html`/`copy_form.html` для необязательных полей
  используется `{{ x if x is not none else '' }}`, а не просто `{{ x }}` —
  иначе Jinja2 рендерит пустое (`None`) поле как буквальный текст "None".
  Использовать `is not none`, а не `x or ''`, для числовых полей вроде
  `acquisition_price` — иначе легитимный `0` тоже превратится в пустую
  строку.
- Публичные и защищённые роуты будут разделены на уровне `APIRouter`
  (`dependencies=[Depends(require_owner)]` на весь роутер, не на отдельные
  функции) — см. "Аутентификация" (шаг 5).
- `app/models/__init__.py` должен импортировать все модели — иначе Alembic
  autogenerate молча не увидит новую таблицу (актуально с шага 2).
- Только `app/services/extraction/*_provider.py` импортируют SDK конкретных
  AI-провайдеров (`anthropic`, `openai`) — остальной код работает только
  через `ExtractionService` Protocol (шаг 4).
- `provider_credentials` — без `user_id` (расхождение с ранним черновиком
  этого документа): таблицы `users` ещё нет (шаг 5), а вся авторизация в
  проекте — на уровне роутера, не строк; колонка-владелец, всегда
  указывающая на единственную строку `users`, не давала бы поведения взамен
  сложности. Вместо неё — глобальный partial unique index (не более одной
  `is_active=true` строки).
- Черновики фото для AI (шаг 4) — временные файлы на диске
  (`data/photos/_drafts/{draft_id}/`), не строки в `photos`: `Photo.copy_id`
  и `Copy.edition_id` — NOT NULL, `Edition.title` — NOT NULL без default, так
  что строка-черновик потребовала бы либо ослаблять эти constraints, либо
  заводить `status`/`is_draft` на `Copy`, который пришлось бы не забывать
  фильтровать везде (список изданий, поиск, витрина) до конца проекта.
  `draft_id` — 32 hex-символа (`secrets.token_hex(16)`); `photo_storage.py`
  проверяет формат при каждом обращении (`InvalidDraftIdError`) — он приходит
  из URL (`/admin/extract/{draft_id}/confirm`, `/media/drafts/{draft_id}/{kind}`),
  то есть от клиента, и без проверки был бы path traversal.
- AI-извлечение (Claude и OpenAI-совместимые) получает структуру ответа через
  **forced tool-choice** (`tool_choice` на конкретную функцию, `strict: true`
  на схеме), а не через prompt-JSON или `output_config.format` — работает с
  произвольной моделью, которую впишут строкой в настройках, и не требует
  `json.loads()` вручную у Claude (у OpenAI-совместимых `function.arguments`
  всё же приходит JSON-строкой — разница учтена в каждом провайдере).
  Список полей/JSON-схема/парсинг ответа — общие для всех провайдеров,
  живут в `app/services/extraction/base.py`, чтобы не разъезжались.
- **Gemini не нуждается в отдельном `gemini_provider.py`**: у неё есть
  OpenAI-совместимый эндпоинт (`https://generativelanguage.googleapis.com/v1beta/openai/`),
  который поддерживает и картинки, и forced tool-choice — значит
  `openai_compatible_provider.py` закрывает Gemini, Groq и саму OpenAI одним
  кодом (не 3 реализации, а 2 после Claude). Groq тоже подтверждён рабочим
  вариантом (forced tool-choice, до 5 фото за запрос, бесплатный тариф) — в
  отличие от Cerebras, у которого нет forced tool-choice и лимит 2 фото на
  бесплатном тарифе (нам нужно 3).
- Ошибки типа "сервис не настроен" (`EncryptionNotConfiguredError` из
  `crypto.py`, когда `SETTINGS_ENCRYPTION_KEY` не задан) обязательно ловятся
  на границе роутера и превращаются в понятный `HTTPException` — поймали
  живьём при первой попытке сохранить настройки: без обработки это была
  голая "Internal Server Error" вместо "переменная не задана".
- Sync SQLAlchemy, не async — при реальной нагрузке (один владелец + случайные
  посетители витрины) async ничего не даёт, только усложняет.
- Без нативных Postgres ENUM — везде `varchar` + Python `enum.Enum` на уровне
  приложения (ENUM-типы болезненно менять миграциями).

## Модель данных (шаги 2, 4, 5, 6)

**`users`** — ровно одна строка, создаётся CLI, регистрации нет:
`id, email, password_hash (Argon2id), last_login_at, created_at/updated_at`.

**`provider_credentials`** — настройки AI-провайдера (в БД, не в `.env`, так
как idea.md хочет выбор провайдера "в настройках"):
`id, provider (строка: claude|openai|gemini|openai_compatible), display_name,
api_key_encrypted (Fernet), base_url, model_name, is_active, created_at,
updated_at` (+ частичный уникальный индекс: не более одной `is_active=true`
строки — без `user_id`, см. "Ключевые решения").

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
Остальные снимки (титул, оборот титула и т.д.) — вход для AI-извлечения и
**не попадают в `photos` вообще** (шаг 4): пока запись не подтверждена, они
лежат как обычные файлы в `data/photos/_drafts/{draft_id}/`, вне БД. После
подтверждения обложка промоутится в постоянное хранилище через тот же
`photo_storage.save_cover_photo`, что и у ручного добавления экземпляра, а
остальные файлы черновика удаляются вместе с папкой. Незавершённые черновики
(фото загружены, запись не подтверждена) чистит фоновый asyncio-цикл в
`main.py` (`sweep_abandoned_drafts`, раз в 6 часов, порог 48 часов,
отключается флагом `enable_draft_cleanup_loop` в тестах) — чистая развёртка
файловой системы по mtime, без обращения к БД. Отдельная видимость по фото
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

## `ExtractionService` (шаг 4) — реализовано

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
    subtitle: ExtractedField | None = None
    authors: ExtractedField | None = None
    original_title: ExtractedField | None = None
    publisher: ExtractedField | None = None
    publication_year: ExtractedField | None = None
    publication_year_text: ExtractedField | None = None
    isbn: ExtractedField | None = None
    language: ExtractedField | None = None
    series: ExtractedField | None = None
    edition_statement: ExtractedField | None = None
    physical_description: ExtractedField | None = None
    description: ExtractedField | None = None
    provider_name: str
    model_name: str
    raw_response: str | None = None   # только для аудита, не для показа
    warnings: list[str] = []

class ExtractionService(Protocol):
    provider_name: str
    def extract(self, images: list[ExtractionImage], *, language_hint: str = "ru") -> ExtractionResult: ...
```

Две реализации, не три (см. "Ключевые решения" — Gemini закрывается тем же
OpenAI-совместимым кодом):
- `claude_provider.py` — `anthropic.Anthropic`, forced tool-choice
  (`tool_choice={"type": "tool", "name": ...}`), `tool_use.input` уже
  распарсен SDK.
- `openai_compatible_provider.py` — `openai.OpenAI(base_url=...)`, forced
  tool-choice (`tool_choice={"type": "function", "function": {"name": ...}}`),
  `function.arguments` — JSON-строка, парсится вручную. Проверен вживую на
  реальном Gemini-ключе через `https://generativelanguage.googleapis.com/v1beta/openai/`
  и на списке моделей Groq (`https://api.groq.com/openai/v1`).
- `base.py` — общий для обоих: список полей `FIELDS`, JSON-схема параметров
  инструмента (`build_tool_parameters_schema`), инструкции промпта,
  `parse_tool_input` (строит `ExtractedField(None, None)`, а не голый `None`,
  когда provider в strict-режиме прислал `{"value": null, "confidence": null}`
  — так делают И Claude, И OpenAI-совместимые).

Ни один провайдер не форсирует `thinking`/`effort` — параметры не
выставляются вовсе, чтобы работать с произвольной моделью, которую вписали
строкой в настройках (часть моделей 400-ит на неизвестных им параметрах).

Предобработка фото — в `photo_storage.py`, разными профилями: черновики для
AI ресайзятся до `DRAFT_MAX_DIMENSION=2400` (старым титульным листам нужно
разрешение для OCR), сама обложка при промоушене в постоянное хранилище —
до `MAX_DIMENSION=1600`, тем же путём, что и у ручного добавления экземпляра
(единообразие независимо от источника).

Хранение настроек — таблица `provider_credentials`, ключи шифруются
`cryptography.fernet.Fernet` с ключом из `SETTINGS_ENCRYPTION_KEY` (env,
никогда не в БД). Форма `/admin/settings` управляет ровно одной строкой
(find-or-create, `is_active` всегда `true`) — многопровайдерный UI
(список/активация) не нужен, пока провайдеров реально используется один за
раз; поле API-ключа в форме всегда пустое, "оставить пустым — не менять".

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
10. Каталоги моделей у провайдеров расходятся с документацией быстрее, чем
    она обновляется — на живом тесте модель из документации Google
    (`gemini-3-flash`) не нашлась в реальном списке, пришлось запрашивать
    `/v1beta/openai/models` напрямую. Не жёстко прошивать имя модели нигде —
    оно всегда пользовательский текстовый ввод, именно на этот случай.
