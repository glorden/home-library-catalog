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
- [x] Шаг 5 — аутентификация, витрина и защита AI-ключа от перерасхода
      (проверено вживую: `docker compose up --build`, две миграции —
      `users`+`copies.is_public` и `extraction_calls` — применены и
      накатаны/откачены в контейнере; `create-admin`/`reset-admin-password`
      выполнены через CLI в контейнере с реальным вводом пароля; логин →
      доступ к `/admin/*` → логаут → повторный запрет проверены в браузере;
      отдельно проверен htmx-нюанс — `hx-delete` на инвалидированной
      (`reset-admin-password`) сессии вернул `200` + `HX-Redirect: /login`,
      обычный запрос на ту же сессию — `303` на `/login`, подтверждено, что
      `HX-Redirect` игнорируется htmx именно на 3xx (см. документацию,
      "Ключевые решения" ниже); `is_public` на экземпляре скрывает издание
      с витрины и отдаёт 404 на `/media/photos/{id}` анонимному
      посетителю (владельцу — отдаёт), прямой подбор `/catalog/{id}`
      приватного издания — тоже 404; `SHOWCASE_PUBLIC=false` закрывает
      витрину целиком; дневной лимит AI-вызовов проверен на реальном
      Gemini-ключе (не тестовым моком) — первый вызов прошёл и
      залогировался в `extraction_calls` с реальными токенами, второй при
      `AI_EXTRACTION_DAILY_LIMIT=1` отдал `429` без обращения к провайдеру;
      61/61 тест проходит. По дороге найден и исправлен баг: чекбокс
      `is_public` в форме экземпляра визуально снимался, но бэкенд всегда
      сохранял `true` — `Form(True)` как дефолт парсинга ошибочно совпадал
      с "чекбокс не пришёл", а непришедший чекбокс означает "снят", а не
      "оставить как в модели"; исправлено на `Form(False)`, как у
      `has_autograph`/`has_ex_libris` — дефолт "публично" живёт только в
      `checked` шаблона, не в бэкенде. Второй найденный по дороге гэп:
      `AI_EXTRACTION_DAILY_LIMIT` не был прокинут в `docker-compose.yml` —
      значение из `.env` тихо игнорировалось контейнером; добавлена
      строка `environment:` по образцу `SESSION_SECRET_KEY`/
      `SHOWCASE_PUBLIC`)
- [x] Шаг 6 — поиск и дедупликация (проверено вживую: `docker compose up
      --build`, миграция применена и накатана/откачена/накатана обратно в
      контейнере; реальный `INSERT` подтвердил, что `search_vector`
      заполняется сервером сам (`GENERATED ALWAYS AS ... STORED`),
      `similarity()` и `websearch_to_tsquery`/`ts_rank` работают на
      Postgres 16.14; в браузере — создание похожего издания показывает
      предупреждение о дубликате без перезагрузки страницы (ссылка на
      существующее издание открывается в новой вкладке, сохранение всё
      равно проходит — не блокирует), редактирование издания не находит
      само себя, но находит другой реальный дубликат; поиск в
      `/admin/editions` и на витрине фильтрует список без перезагрузки
      (`hx-select`), очистка поля возвращает полный список, приватное
      издание не находится через публичный поиск (в т.ч. по точному
      названию), закрытая витрина (`SHOWCASE_PUBLIC=false`) не отдаёт
      результатов поиска; живой ввод дореформенной орфографии (ѣ, і, ѳ, ъ)
      не даёт 500-й. 91/91 тест проходит (было 61 на шаге 5). По дороге
      сверочный агент (отдельный проход перед реализацией) нашёл настоящий
      баг ещё на бумаге — `DISTINCT` несовместим с `ORDER BY ts_rank(...)`,
      которого нет в списке `SELECT`, — обойдено через
      `Edition.id.in_(subquery)` вместо `JOIN + DISTINCT`; отдельно один из
      автотестов поймал живой баг уже в реализации: `normalize_text`
      вырезала пунктуацию вместо замены на пробел, из-за чего "Толстой
      Л.Н." и "Толстой Л. Н." давали разные fingerprint — см. "Ключевые
      решения")
- [x] Шаг 7 — PWA (проверено вживую: `docker compose up --build` с нуля —
      Dockerfile корректно упаковывает иконки/манифест/`sw.js`/
      `offline.html` без изменения самого Dockerfile, это обычные
      закоммиченные файлы, а не build-артефакты; service worker
      регистрируется на корневом пути `/sw.js` (не `/static/sw.js` — иначе
      scope не покрыл бы навигации), реально активируется и переходит под
      `clients.claim()`. Cache-first для статики подтверждён не моком, а
      честной остановкой контейнера `app` (`docker compose stop`) — иконка
      всё равно отдалась `200` из кэша; в это же время не-навигационный
      запрос (как у htmx) корректно упал `Failed to fetch`, а не
      подменился офлайн-страницей — обе половины риска №4 проверены
      раздельно, настоящая навигация в тот же момент отдаёт закэшированный
      `/offline.html`. После восстановления сервера — настоящий htmx-поиск
      на витрине (`keyup` → `200` на `/?q=...`, `hx-push-url` сработал) и
      dedup-candidates в админке (шаг 6) отработали без изменений при
      активном SW. Версионирование кэша проверено принудительной сменой
      `CACHE_VERSION`: старая версия и посторонний подложенный кэш
      удаляются при `activate`, остаётся только текущая версия. 99/99
      тестов (было 91; `tests/test_pwa.py` — манифест, обе purpose иконок,
      geometric-проверка safe zone маскируемой иконки, favicon с тремя
      размерами, корневой scope `sw.js`, офлайн-страница, теги в
      `base.html`). Реальный тест "добавить на экран" с телефона по Wi-Fi
      отложен до шага 8 — SW вне localhost требует HTTPS; критерии
      устанавливаемости (валидный манифест, активный контролирующий SW,
      secure context) подтверждены на localhost)
- [x] Шаг 8 — деплой на VPS (проверено вживую на настоящем сервере —
      Ubuntu 24.04, домен `book.glorden.ru`, реальный сертификат Let's
      Encrypt — а не локальной имитацией). Черновик предполагал
      nginx+Certbot; заменено на Caddy — автоматический HTTPS без ручного
      bootstrap-сертификата, и нашёлся нативный эквивалент
      `X-Accel-Redirect` через `reverse_proxy`+`handle_response`/`intercept`
      (синтаксис заранее проверен `caddy validate` на собранном образе, не
      только по документации); rate limiting `/login` — не входит в ядро
      Caddy, собран кастомный бинарник через `xcaddy` с
      `mholt/caddy-ratelimit`. `docker-compose.prod.yml` пришлось делать не
      overlay-парой, а тремя файлами: эмпирически проверено (`docker
      compose config` на тестовых файлах), что `ports`/`volumes`
      накапливаются между `-f`-файлами, а не заменяются — dev-порты и
      dev-биндмаунты исходников вынесены в новый `docker-compose.override.yml`
      (подхватывается автоматически голым `docker compose up`, `make dev`
      не изменился), базовый `docker-compose.yml` остался общим и
      минимальным (`DEBUG` дефолт перевёрнут на `false` — безопасно, даже
      если прод-оверлей забудут указать).

      VPS-хардненинг тоже сделан и проверен вживую: `deploy`-пользователь
      (sudo, группа `docker`) по образцу уже существующей на этой машине
      конвенции для другого проекта; UFW (22/80/443, остальное — deny);
      Docker Engine + Compose plugin; sshd переведён на ключи — вживую
      найден реальный конфликт двух provider-конфигов
      (`50-cloud-init.conf` разрешал пароль, `60-cloudimg-settings.conf`
      запрещал, побеждал первый по sshd `first-match-wins`) — решено
      добавлением своего файла с более ранней сортировкой, а не правкой
      чужих; после `reload` подтверждено отдельно: вход по ключу работает,
      попытка парольного входа получает `Permission denied (publickey)`.
      `apt dist-upgrade` уткнулся в интерактивный conffile-вопрос по
      `/etc/cloud/cloud.cfg` (провайдерская кастомизация, не трогать) —
      разрешено флагом `--force-confold`, затем реальный ребут на новое
      ядро с живой проверкой, что SSH поднялся обратно.

      По дороге — несколько живых инцидентов, а не гладкий прогон:
      1 ГБ RAM у VPS не хватало на `go build` внутри `xcaddy` (сборка
      Caddy) — добавлен 2 ГБ swap и почищен build cache (диск подходил
      к 80%). SSH-клиент дважды рвался с exit 255 на длинных "тихих"
      командах — сама сборка на демоне Docker при этом не прерывалась
      (подтверждено: `docker images` показывал готовый образ уже после
      "упавшей" сессии); решение — гонять сборки полностью отсоединённо
      (`nohup`+`disown`, лог в файл на VPS) и опрашивать короткими
      SSH-подключениями вместо одного долгоживущего. Первый прогон на
      свежей БД отдал `500` (`relation "editions" does not exist`) —
      забыли `alembic upgrade head`, применили, поправилось. Настоящий баг
      найден на первом реальном фото: `media.py` слал
      `X-Accel-Redirect: /internal-media/<path>` по аналогии с nginx, где
      этот префикс называет отдельный `internal;`-роут — но у Caddy
      `handle_response` не отдельный внешний роут, а реакция внутри того
      же уже проверенного запроса, отдельного `/internal-media/*` в
      Caddyfile просто нет, и `file_server` промахивался мимо реального
      пути на один сегмент. Публичная обложка отдавала `404` при
      `is_public=true` и существующем файле — почищен префикс, фикс
      выкачен на прод, тесты и `ruff` перепрогнаны (99/99, чисто).

      Полная матрица проверена через настоящий Caddy, не заглушку:
      HTTP→HTTPS редирект (`308`), витрина без входа, `/login` пускает 5
      запросов и отдаёт `429` на 6-й и далее, публичное фото — реальные
      байты (JPEG-заголовок, размер файла совпадает) анонимному
      посетителю, приватное — `404` анонимному и `200` владельцу через
      `/admin/editions/{id}` (а вот `/catalog/{id}` отдаёт `404` даже
      владельцу для приватного экземпляра — это не баг, а осознанный
      дизайн публичной витрины, см. "Ключевые решения"); вход владельца
      и полная работа админки — с реального компьютера и телефона.
      Отдельно — то единственное, что нельзя было проверить на шаге 7 без
      HTTPS: Service Worker регистрируется на боевом домене без ошибок,
      манифест валиден (Chrome предлагает необязательные `screenshots` для
      "richer install UI" — не ошибка), и «добавить на экран» с реального
      телефона работает — иконка появляется, приложение открывается без
      адресной строки.

      Бэкапы (pg_dump + фото за пределы VPS) сознательно вынесены за рамки
      этого шага — отдельная задача после MVP, здесь не проектировались и
      не настраивались. 99/99 тестов, `ruff` чист.
- [x] Шаг 9 — AI-провайдер из заблокированной страны (подробности —
      DEPLOY.md, "Шаг 9"). Обнаружено при реальном пользовательском
      тестировании: прод-VPS геолоцирован в России, а Gemini упал живьём с
      `400 FAILED_PRECONDITION: "User location is not supported"`. Смена
      провайдера не помогла бы — WebSearch подтвердил, что Россия
      исключена из supported-countries и у Anthropic, и у OpenAI, и у
      Google.

      Решение — SOCKS5-туннель (SSH `-D`) на уже существующий VPS во
      Франции (там уже крутился не связанный с проектом Xray/x-ui —
      обнаружено при разведке, учтено: `sshd_config` того сервера не
      трогали, только добавили изолированного `tunneluser` без шелла).
      `docker/ai-proxy` — сайдкар только в проде, `registry.py` — единая
      точка, где собирается `httpx.Client(proxy=...)` и прокидывается в
      оба провайдера через `http_client=`. Реально проверено (не мок):
      сначала сам туннель (`ssh -f -N -D` + `curl` через него — вышел в
      интернет из Парижа), затем тот же код из `registry.py` внутри
      прод-контейнера (`icanhazip.com` через `socks5h://ai-proxy:1080` —
      IP реально парижский), негативный тест (`docker compose stop
      ai-proxy` → чистый `httpx.ConnectError`, не зависание; `start` —
      восстановилось).

      **Неожиданный результат**: сам туннель не решил проблему с Gemini —
      даже прямой `httpx`-запрос через прокси с настоящим ключом (в обход
      SDK, чтобы исключить баг в обвязке) всё равно получил тот же
      `FAILED_PRECONDITION`. Значит, у Google эта проверка привязана не
      (только) к IP запроса, а похоже что к самому аккаунту/проекту, из
      которого выпущен ключ — туннель такое не обходит, в отличие от
      честной блокировки по сетевому адресу. Проверено на альтернативном
      провайдере (Groq, `qwen/qwen3.6-27b` — единственная vision+tool-use
      модель у них): без туннеля — `403 Forbidden` (похоже на блок на
      уровне CDN/WAF по стране), через туннель — реальный успешный вызов
      с токенами. Вывод: у разных вендоров разный механизм блокировки
      (по IP vs по аккаунту), туннель помогает только с первым типом —
      это не универсальное решение "для любого AI-провайдера", проверять
      нужно каждый отдельно.

## Структура репозитория

```
home-library-catalog/
├── .github/{workflows/ci.yml, ISSUE_TEMPLATE/, dependabot.yml, pull_request_template.md}
├── app/
│   ├── main.py, config.py, database.py, dependencies.py, security.py, cli.py
│   ├── models/{edition.py, copy.py, photo.py, provider_credential.py,
│   │           user.py, extraction_call.py} + __init__.py со ВСЕМИ импортами
│   ├── schemas/extraction.py
│   ├── routers/
│   │   ├── pages.py, auth.py                                   # публичные
│   │   │   (search.py отдельным роутером НЕ создан — см. "Ключевые решения")
│   │   └── admin_editions.py, admin_copies.py, admin_settings.py,
│   │       extraction.py                                      # APIRouter(prefix="/admin/...",
│   │                                                           #   dependencies=[Depends(require_owner)] — шаг 5, готово)
│   ├── services/
│   │   ├── extraction/{base.py, claude_provider.py,
│   │   │                openai_compatible_provider.py, registry.py}
│   │   ├── photo_storage.py, crypto.py, extraction_log.py, dedup.py, search.py
│   ├── templates/{base.html, pages/ (+ offline.html), admin/*}
│   └── static/{css/input.css, css/output.css (сгенерирован),
│                js/htmx.min.js (скачан), js/sw.js, icons/, manifest.json}
├── alembic/*  {env.py, versions/}
├── scripts/generate_pwa_icons.py
├── tests/{conftest.py, test_*.py}
├── docker/app/Dockerfile, docker/caddy/*  (Caddy — шаг 8)
├── docker-compose.yml, docker-compose.override.yml, docker-compose.prod.yml
├── pyproject.toml, Makefile
└── LICENSE, README.md, README.en.md, ARCHITECTURE.md, DEPLOY.md, PROCESS.md
```

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
- Публичные и защищённые роуты разделены на уровне `APIRouter`
  (`dependencies=[Depends(require_owner)]` на весь роутер, не на отдельные
  функции) — см. "Аутентификация" (шаг 5).
- `app/models/__init__.py` должен импортировать все модели — иначе Alembic
  autogenerate молча не увидит новую таблицу (актуально с шага 2).
- Только `app/services/extraction/*_provider.py` импортируют SDK конкретных
  AI-провайдеров (`anthropic`, `openai`) — остальной код работает только
  через `ExtractionService` Protocol (шаг 4).
- `provider_credentials` — без `user_id` (расхождение с ранним черновиком
  этого документа): на момент этого решения (шаг 4) таблицы `users` ещё не
  было, а вся авторизация в проекте — на уровне роутера, не строк;
  колонка-владелец, всегда указывающая на единственную строку `users`, не
  давала бы поведения взамен сложности. Вместо неё — глобальный partial
  unique index (не более одной `is_active=true` строки).
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
- **Поиск без отдельного `routers/search.py`** (расхождение с ранним
  наброском этого документа, шаг 6): вместо отдельной страницы/роутера
  существующие `pages.py::home` и `admin_editions.py::list_editions`
  получили параметр `q`, а на клиенте используется htmx `hx-select` —
  вытягивание фрагмента (`#editions-table-body`/`#catalog-grid`) из ответа
  на обычный GET того же URL, без серверной ветки "это htmx-запрос или
  обычная навигация". Отдельная страница дублировала бы уже готовую в
  `home()` логику видимости/обложек/шаблона без реальной выгоды —
  `hx-push-url` на `/?q=...` даёт такую же шэримую ссылку, как отдельный
  `/search?q=...` был бы.
- **`dedup_fingerprint` заполняется явным вызовом `dedup.apply_fingerprint()`
  в роутерах** (`create_edition_from_form`, `update_edition`), а не через
  SQLAlchemy `@validates`/`before_insert`-события, хотя это выглядело бы
  более "централизованным" решением: проверено эмпирически, что SQLModel
  0.0.39 переприменяет дефолты всех полей уже ПОСЛЕ того, как `@validates`
  отработал при конструировании (`Edition(**kwargs)`) — `@validates` тихо
  обнулял бы fingerprint обратно в `None` именно при СОЗДАНИИ записи
  (на редактировании работал бы правильно), то есть ломался бы ровно там,
  где баг сложнее всего заметить. Явный вызов в местах мутации — тот же
  принцип, что уже применяется для `updated_at`/`extraction_log.log_call`.
- **Нормализация под fingerprint заменяет пунктуацию на пробел, а не
  вырезает её**: вырезание превращало бы "Толстой Л.Н." (без пробела между
  инициалами) и "Толстой Л. Н." (с пробелом) в РАЗНЫЕ fingerprint — без
  пробела-разделителя инициалы склеивались в "лн" и переставали совпадать с
  "л н". Пойман автотестом, который изначально ожидал равенство этих двух
  вариантов — тест был прав, а не код.
- **pg_trgm-сравнение в `find_candidates` использует лёгкую нормализацию**
  (только `lower()` с обеих сторон), а НЕ ту же тяжёлую (NFKC + ё→е + без
  пунктуации), что у fingerprint: сравнение должно соответствовать тому,
  что реально проиндексировано (`lower(title) gin_trgm_ops`), а триграммное
  сходство и так толерантно к мелким отличиям по своей природе. Порог —
  `0.3`, совпадает с дефолтным GUC `pg_trgm.similarity_threshold` (типовая
  отправная точка, требующая подстройки на реальных данных — риск №1).
- **ISBN как сигнал дедупа сравнивается через `regexp_replace(col,
  '[^0-9Xx]', '', 'g')` с обеих сторон**, а не напрямую — иначе разная
  расстановка дефисов ("978-5-699-10138-8" vs "9785699101388") ломает то,
  что должно быть самым надёжным сигналом. Формат хранения `editions.isbn`
  при этом не меняется (как ввели на шаге 2, так и хранится).
- **`search_editions` с `public_only=True` использует
  `Edition.id.in_(select(Copy.edition_id).where(...))`, а не `JOIN Copy +
  .distinct()`**: при сортировке по `ts_rank(...)` (не входит в список
  `SELECT`) Postgres не разрешает `DISTINCT` — `ERROR: for SELECT DISTINCT,
  ORDER BY expressions must appear in select list`. Подзапрос через `IN`
  не требует `DISTINCT` вовсе (внешний запрос и так вернёт одну строку
  `Edition` на id, сколько бы `Copy` у него ни было) и попутно устраняет
  саму возможность этой ошибки, а не только чинит её здесь.
- **`editions.search_vector` — Postgres `GENERATED ALWAYS AS (...) STORED`
  колонка** (`sqlalchemy.Computed`, а не Python-логика): заполняется
  сервером на каждом `INSERT`/`UPDATE` сам, приложение никогда в неё не
  пишет. Ровно поэтому `SQLModel.metadata.create_all()` (которым
  пользуются тесты, `tests/conftest.py` не гоняет Alembic) и сама миграция
  дают одинаковую схему — `Computed()` компилируется в DDL на уровне
  самой колонки, а не через autogenerate-диффинг.
- **`tests/conftest.py` сам ставит `CREATE EXTENSION IF NOT EXISTS
  pg_trgm`** в `library_test` (в `_ensure_test_database_exists()`) — тесты
  не гоняют Alembic-миграции, значит расширение (и функцию `similarity()`)
  неоткуда взять, кроме как поставить его отдельно для тестовой БД.

## Модель данных (шаги 2, 4, 5, 6)

**`users`** — ровно одна строка, создаётся CLI, регистрации нет:
`id, email, password_hash (Argon2id), session_version (int, инкрементируется
при reset-admin-password — инвалидирует ранее выданные session cookie),
last_login_at, created_at/updated_at`.

**`provider_credentials`** — настройки AI-провайдера (в БД, не в `.env`, так
как idea.md хочет выбор провайдера "в настройках"):
`id, provider (строка: claude|openai|gemini|openai_compatible), display_name,
api_key_encrypted (Fernet), base_url, model_name, is_active, created_at,
updated_at` (+ частичный уникальный индекс: не более одной `is_active=true`
строки — без `user_id`, см. "Ключевые решения").

**`extraction_calls`** — лог каждой попытки AI-распознавания (шаг 5, защита
от перерасхода): `id, created_at, provider, model_name, image_count, success,
tokens_input, tokens_output, error_message`. Без `user_id` и без индексов —
та же логика, что у `provider_credentials` (один пользователь, личный
масштаб данных). Используется и для дневного лимита
(`AI_EXTRACTION_DAILY_LIMIT`), и как аудит-лог токенов.

**`editions`** (библиографическая запись), базовые поля — шаг 2:
`id, title, subtitle, authors (свободный текст — см. риски), original_title,
publisher, publication_year (smallint), publication_year_text ("1930-е",
"б.г."), isbn (индекс), language, series, edition_statement,
physical_description, description, created_at, updated_at`.
Отдельной миграцией на шаге 6 добавлены `dedup_fingerprint` (btree-индекс,
заполняется приложением) и `search_vector` (generated tsvector, GIN,
`'russian'`, заполняется сервером — веса: title/authors — `A`, subtitle/
original_title/series — `B`, publisher — `C`, description — `D`; `isbn` в
`search_vector` не входит — у него свой точный путь сравнения, не
полнотекстовый). Бэкофилл существующих строк — в самой миграции, через
`sa.table()`-прокси (не через ORM-класс `Edition`, чтобы не завязываться на
его будущую форму) и живой `dedup.compute_fingerprint` (на момент миграции
строк в БД не было, но код на этот случай корректен).

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

**Дедупликация** (шаг 6, реализовано): `dedup_fingerprint =
normalize(title)|normalize(author)|year` (NFKC, lowercase, ё→е, пунктуация →
пробел + схлопывание пробелов) + точное совпадение ISBN (нормализовано от
дефисов) + `pg_trgm` similarity по title как третий сигнал. Все три сигнала
и очередь приоритета при пересечении (isbn → fingerprint → title_similarity)
— в `app/services/dedup.py::find_candidates`. Кандидаты показываются в
`edition_form.html` (создание и редактирование, с исключением себя через
`exclude_edition_id`) и `extraction_confirm.html` (AI-подтверждение) через
htmx: эндпоинт `GET /admin/editions/dedup-candidates` дёргается на каждое
изменение title/authors/publication_year/isbn (`keyup changed delay:500ms,
change`), title дополнительно триггерит запрос на `load` (первоначальное
наполнение без ожидания первого ввода) — специально на `title`, а не на сам
`#dedup-candidates`, потому что тот получает свежую копию себя при каждом
свапе, и триггер `load` на нём же вызвал бы бесконечную цепочку
самозапросов. Кандидаты только предлагаются — сохранение работает
независимо от их наличия, автослияния нет.

**Фото и Caddy**: если реверс-прокси отдаёт `/media/*` напрямую, `is_public`
теряет смысл — решение `X-Accel-Redirect` (FastAPI проверяет права → просит
Caddy отдать файл: `reverse_proxy` + `handle_response`/`intercept` на этот
заголовок + `file_server`, см. DEPLOY.md, шаг 8). В отличие от nginx
`internal;`-location, у Caddy это не отдельный внешний роут — реагирует
только вложенный `handle_response` того же уже проверенного запроса, так
что значение заголовка — просто путь относительно смонтированного тома, без
служебного префикса (на шаге 8 он сначала был добавлен по nginx-привычке и
сломал реальную раздачу фото — поймано вживую, см. статус шага 8).

## Поиск (шаг 6) — реализовано

`app/services/search.py`: `search_editions(session, query, *, public_only,
limit=50)` — пустой/пробельный `query` пропускает `websearch_to_tsquery`
целиком и просто сортирует по `title` (передача `''` в
`websearch_to_tsquery` даёт пустой tsquery, который не матчит вообще
ничего); непустой — `search_vector @@ websearch_to_tsquery('russian', ...)`
с сортировкой по `ts_rank(...) DESC`. `covers_for_editions(session,
editions)` — батч-подбор обложки первого публичного экземпляра на издание
(без параметра `public_only` — единственный вызывающий уже только
публичный, см. "Ключевые решения").

UI — не отдельная страница, а `q`-параметр на уже существующих `GET /` и
`GET /admin/editions` + htmx `hx-select` на стороне клиента (см. "Ключевые
решения" про отказ от `routers/search.py`). Админка видит вообще все
издания; витрина — только с публичным экземпляром, и не находит приватные
даже по точному совпадению названия в поиске (то же правило видимости, что
и у обычного просмотра каталога).

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

## Аутентификация (шаг 5) — реализовано

Подписанная session-cookie + одна строка в `users`, без ролей/permissions.

- `app/security.py`: `create_session_cookie` / `verify_session_cookie`
  (itsdangerous, HMAC). Подписывается не только `user_id`, но и
  `users.session_version` (не было в исходном черновике этого раздела) —
  без server-side хранилища сессий подписанную cookie иначе нечем отозвать
  досрочно: `reset-admin-password` инкрементирует version, тем самым
  инвалидируя все ранее выданные cookie сразу же, а не только через
  30 дней естественного истечения.
- `app/dependencies.py`: `get_current_user` (может вернуть `None`) и
  `require_owner` (кидает ошибку, если `None`).
- Защищённые роутеры: `APIRouter(prefix="/admin/...",
  dependencies=[Depends(require_owner)])` — забыть защитить один эндпоинт
  становится структурно невозможно.
- **htmx-нюанс**: обычный редирект на `/login` в ответ на htmx-запрос
  воткнётся как фрагмент внутрь страницы — сломанный UX. Нужен обработчик,
  отвечающий заголовком `HX-Redirect: /login` при `HX-Request: true` вместо
  обычного `RedirectResponse`. **Проверено** по актуальной документации
  (htmx.org/headers/hx-redirect/, не по памяти): "Response headers are not
  processed on 3xx response codes" — обработчик обязан отвечать `200` на
  htmx-ветке, обычный `RedirectResponse(303)` для неё не подходит.
- Пароль — Argon2id (`argon2-cffi`).
- Bootstrap единственного аккаунта — Typer CLI: `create-admin`,
  `reset-admin-password` (восстановление без email-инфраструктуры).
- CSRF: на MVP достаточно `SameSite=Lax` + `Secure` + `HttpOnly`; явный
  CSRF-токен — post-MVP усиление.
- Rate limiting `/login` — на уровне Caddy (модуль `mholt/caddy-ratelimit`,
  собран в кастомный образ через `xcaddy`), без дополнительных
  Python-зависимостей.

## PWA (шаг 7) — реализовано

Не offline-first (данные должны быть свежими), а устанавливаемая оболочка:

- `app/static/manifest.json` — иконки 192/512 (purpose "any") + отдельная
  maskable 512×512 (глиф в безопасной зоне — вписанном круге радиусом 40%
  стороны иконки — с запасом ~29%, проверено геометрически в
  `tests/test_pwa.py`), `theme_color` = акцентный `#4f46e5` проекта (тот
  же, что у всех кнопок `type="submit"`). `apple-touch-icon`/`icon`/
  `manifest` ссылки и `apple-mobile-web-app-*` мета-теги — в `base.html`
  (iOS не полностью следует manifest, нужен отдельный тег).
- Иконки (192/512/maskable-512/apple-touch-icon/favicon.ico с тремя
  вложенными размерами 16/32/48) генерируются локально скриптом
  `scripts/generate_pwa_icons.py` на Pillow — без сторонних сервисов
  генерации favicon/манифеста, тот же принцип, что уже применён к
  `htmx.min.js` и Tailwind (см. "Ключевые решения").
- `app/static/js/sw.js`, отдаётся роутом `GET /sw.js` **с корневого пути**
  (не `/static/sw.js`) — scope service worker'а по умолчанию равен
  директории, откуда он отдан; под `/static/` он не смог бы перехватывать
  навигации на `/`, `/catalog/*` и т.д. Роут читает файл с диска на каждый
  запрос (не кэширует в Python) — правки подхватываются без перезапуска.
- `fetch`-обработчик — ровно две ветки, всё остальное не перехватывается
  вообще: `request.mode === 'navigate'` → network-first с fallback на
  закэшированный `/offline.html`; same-origin `/static/*` → cache-first.
  **Критично** (риск №4): без проверки `request.mode` SW подставлял бы
  `/offline.html` внутрь htmx partial-ответов — проверено вживую (см.
  статус шага выше), htmx-поиск и dedup-candidates (шаг 6) не заметили
  активный SW. `CACHE_NAME` версионируется (`library-shell-{версия}`),
  `activate` удаляет все кэши с чужим именем.
- `docker-compose.yml`: `app/static` в dev не примонтирован целиком (см.
  "Ключевые решения", шаг 3) — `icons/`, `manifest.json` и
  `static/js/sw.js` примонтированы точечно тем же способом, чтобы правки
  не требовали `--build` на каждую итерацию.
- Камера: `<input type="file" accept="image/*">` — **без** `capture="environment"`.
  Атрибут стоял с шага 3 и был снят после реального мобильного тестирования на
  шаге 8: он заставляет мобильный браузер сразу открывать камеру в обход
  системного чузера, так что выбрать существующее фото из галереи было нельзя.
  Без `capture` чузер показывает оба варианта (камеру и галерею), `accept`
  по-прежнему фильтрует на изображения. HEIC с айфонов (`pillow-heif`,
  ресайз/EXIF-strip только серверный) — по-прежнему с шага 3, не менялось.
- На той же волне тестирования: в форме «Добавить книгу по фото»
  (`extract_upload.html`) обязательна только обложка — титульный лист и его
  оборот помогают точности распознавания, но не обязательны. Бэкенд
  (`app/routers/extraction.py`) принимает их как `UploadFile | None` тем же
  приёмом, что и `cover_photo` в `admin_copies.py` (см. выше); в
  `extraction_confirm.html` превью показывает только реально загруженные фото
  черновика — без этого отсутствующий файл давал бы битую картинку (404 на
  `/media/drafts/{id}/{kind}`).
- HTTPS обязателен для service worker вне localhost — реальный тест
  "добавить на экран" с телефона по Wi-Fi сознательно отложен до шага 8
  (деплоя). Критерии устанавливаемости (валидный манифест, активный
  контролирующий SW, secure context) и весь жизненный цикл SW проверены на
  localhost.

## Риски

1. Порог похожести для дедупа (`TITLE_SIMILARITY_THRESHOLD = 0.3`, шаг 6) —
   стартовое значение = дефолтный GUC `pg_trgm.similarity_threshold`; всё
   равно потребует подстройки на реальных данных, когда книг станет много.
   Дореформенная орфография (ѣ, і, ѳ, ъ) — **проверено**: `normalize_text`
   не падает и не выедает эти буквы (юнит-тесты сверяют символы через
   `unicodedata.name()`, не полагаясь на визуальное сходство с латиницей;
   отдельно проверен живой ввод такого текста в реальную форму в браузере —
   200, без 500-й).
2. AI-стоимость/лимиты — решено на шаге 5: таблица `extraction_calls`
   логирует каждый вызов (провайдер, модель, токены, успех/ошибка), перед
   вызовом — проверка дневного лимита (`AI_EXTRACTION_DAILY_LIMIT`, по
   умолчанию 30), при превышении — 429 с понятным текстом вместо падения.
   Это защита от собственного бага/цикла ("от дурака"), не от постороннего
   — от чужого доступа защищает авторизация (см. "Аутентификация" выше);
   жёсткий лимит трат всё равно стоит поставить в кабинете самого
   AI-провайдера отдельно от кода.
3. Место под фото — умеренный риск (не критичный): долговременно хранится
   только обложка на экземпляр. Но обложки всё равно невосстановимы в
   отличие от БД, а бэкапов вне VPS пока нет — решение сознательно
   отложено на отдельный шаг после MVP (см. DEPLOY.md), и до тех пор это
   реальный открытый риск, а не только гипотетический; плюс не забыть про
   очистку незавершённых черновиков, чтобы служебные снимки не копились
   на диске.
4. Service worker и htmx: перехват только navigation-запросов — иначе SW
   сломает htmx-фрагменты. Механизм и живая проверка обеих сторон риска —
   в разделе PWA выше, не повторяю здесь.
5. Единственный админ-пароль без email-восстановления — `reset-admin-password`
   протестирован вживую на шаге 5 (CLI в контейнере + автотест на
   инвалидацию старой сессии через `session_version`), не только
   спроектирован.
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
