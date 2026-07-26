# Деплой

Шаг 8 выполнен и проверен вживую на настоящем VPS (Ubuntu 24.04, домен
`book.glorden.ru`, реальный сертификат Let's Encrypt) — ниже не план, а то,
что реально сработало, включая найденные по дороге проблемы.

## Переменные окружения

Локальная разработка через `docker compose up` (без `-f`) использует
`docker-compose.yml` + `docker-compose.override.yml` — последний
подхватывается автоматически, задаёт dev-порты/биндмаунты/`--reload` и
`DEBUG=true`. На VPS все секреты задаются через `.env` в корне
репозитория — этот файл никогда не коммитится.

| Переменная | Появилась на шаге | Назначение |
|---|---|---|
| `DATABASE_URL` | 2 | строка подключения к Postgres |
| `SETTINGS_ENCRYPTION_KEY` | 4 | ключ Fernet для шифрования API-ключей AI-провайдеров |
| `SESSION_SECRET_KEY` | 5 | ключ подписи session cookie (itsdangerous, HMAC) |
| `SHOWCASE_PUBLIC` | 5 | `true`/`false` — временно закрыть публичную витрину целиком |
| `AI_EXTRACTION_DAILY_LIMIT` | 5 | дневной лимит вызовов AI-распознавания (по умолчанию 30) |

`DEBUG` в `.env` с шага 8 ни на что не влияет под Docker: значение
захардкожено (`false` в `docker-compose.yml`, `true` в
`docker-compose.override.yml`) — так прод безопасен по умолчанию, даже
если прод-оверлей забудут указать. Переменная в `.env`/`.env.example`
имеет смысл только при локальном запуске без Docker (venv).

`SETTINGS_ENCRYPTION_KEY`/`SESSION_SECRET_KEY` на VPS генерируются заново
(см. процедуру ниже) — значения с локальной машины разработчика на прод не
переносятся.

## Требования к Postgres

Миграция шага 6 сама ставит расширение (`CREATE EXTENSION IF NOT EXISTS
pg_trgm`) — отдельного шага в процедуре деплоя не требуется, но образ
Postgres должен включать contrib-модули. `postgres:16-alpine` (используется
в `docker-compose.yml`) их включает.

## Docker Compose: три файла, не два

`docker compose config` эмпирически подтвердил (на тестовых compose-файлах
перед тем, как переносить решение в проект): `ports` и `volumes`
**накапливаются** между `-f`-файлами, а не заменяются — если dev-порт или
dev-биндмаунт объявлен в базовом файле, прод-оверлей не может его убрать,
просто не упомянув. `environment` и `command`, наоборот, мержатся/
заменяются по ключу — этим можно пользоваться. Отсюда реальная схема:

- **`docker-compose.yml`** — общий минимум для dev и прода: `build`,
  постоянные тома (`db_data`, `./data/photos`), `environment` с безопасным
  дефолтом (`DEBUG: "false"`). Без `ports`, без dev-биндмаунтов исходников,
  без `command` (используется `CMD` из Dockerfile — без `--reload`).
- **`docker-compose.override.yml`** — коммитится в git, секретов не
  содержит. Всё, что нужно только для локальной разработки: `ports`
  (5432, 8000), точечные биндмаунты исходников (см. комментарий в файле —
  почему точечно, а не всей `./app`), `command` с `--reload`,
  `environment: DEBUG: "true"`. Подхватывается автоматически при голом
  `docker compose up`/`make dev` — прод-инвокейшен явно перечисляет только
  два других файла, поэтому этот в прод не попадает.
- **`docker-compose.prod.yml`** — `restart: unless-stopped` на `db`/`app`,
  сервис `caddy`.

Прод всегда запускается явно:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Caddy: HTTPS, X-Accel-Redirect, rate limiting

Изначально планировался nginx+Certbot; по факту — Caddy, и вот почему:

- **Автоматический HTTPS** без ручного bootstrap-сертификата (nginx+Certbot
  потребовал бы отдельного dummy-сертификата для первого старта и
  cron/сайдкара для продления — Caddy делает всё это сам).
- **X-Accel-Redirect-эквивалент есть и в Caddy**, через `reverse_proxy` с
  `handle_response`: сматченный по заголовку `X-Accel-Redirect` ответ
  перехватывается, и `file_server` отдаёт файл напрямую с диска —
  `app/routers/media.py` при этом продолжает быть единственным местом,
  где проверяются права (`is_public`), Caddy только отдаёт байты.
  **Важное отличие от nginx**: `internal;`-location в nginx — отдельный
  внешний роут, который нужно явно защищать от прямого обращения; у Caddy
  `handle_response` — не отдельный роут, а реакция внутри уже
  обработанного (и уже проверенного правами) запроса, снаружи попасть в
  этот код напрямую нельзя в принципе. Из-за этого различия значение
  заголовка — просто `/{file_path}` относительно смонтированного тома, БЕЗ
  служебного префикса вроде `/internal-media/` (изначально был добавлен по
  nginx-привычке и сломал раздачу — путь до файла не совпадал ровно на
  один сегмент; поймано вживую на первом реальном фото, см. ARCHITECTURE.md).
- **Rate limiting `/login` не входит в ядро Caddy** — нужен модуль
  `mholt/caddy-ratelimit`, собираемый в кастомный образ через `xcaddy`
  (`docker/caddy/Dockerfile`, билд-стадия, не рантайм-зависимость).

Ключевые файлы: `docker/caddy/Dockerfile`, `docker/caddy/Caddyfile` (домен
и email для ACME — буквально текстом в файле, шаблонизация не оправдана
для одного фиксированного домена; email опционален для Let's Encrypt,
можно не указывать).

Синтаксис Caddyfile (в т.ч. `rate_limit`/`zone`/`match` и связка
`handle_response`+`rewrite`+`file_server`) стоит проверять `caddy
validate` на собранном образе перед деплоем — это не стоковый `caddy:2`, а
кастомная сборка, и часть директив (rate_limit) в стоковом образе вообще
не распознаётся.

## VPS: базовая настройка

Одноразовая настройка чистого VPS (Ubuntu 24.04, root по SSH):

1. `apt update && apt upgrade -y` (может потребовать `dist-upgrade` отдельно,
   если apt "придержал" пакеты ядра — `apt list --upgradable` покажет).
   На образах с cloud-init возможен интерактивный conffile-вопрос по
   `/etc/cloud/cloud.cfg` (провайдерская кастомизация) —
   `dpkg --configure -a --force-confdef --force-confold` разрешает,
   оставляя провайдерскую версию.
2. Пользователь `deploy` (sudo, группа `docker`) — не работать повседневно
   от root. Публичный ключ — тот же, что и для root (или отдельный,
   на усмотрение).
3. UFW: `ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw
   --force enable` — **именно в этом порядке**, SSH разрешить до `enable`,
   иначе самозаблокировка.
4. Docker Engine + Compose plugin — официальный apt-репозиторий
   (`download.docker.com/linux/ubuntu`), не дистрибутивный пакет.
5. `deploy` в группу `docker` (`usermod -aG docker deploy`) — новая SSH-сессия
   подхватывает группу, старая — нет.
6. sshd — только ключи. **Проверить конфликты в `/etc/ssh/sshd_config.d/*.conf`
   перед добавлением своих настроек**: облачные образы нередко несут
   несколько drop-in файлов, и sshd берёт по правилу first-match-wins
   (первое значение директивы побеждает, а не последнее) — если в системе
   уже есть, например, `50-cloud-init.conf` с `PasswordAuthentication yes`
   и `60-...conf` с `no`, побеждает первый. Решение — свой файл с более
   ранней сортировкой (например, `10-hardening.conf`), а не правка чужих:
   ```
   PasswordAuthentication no
   PermitRootLogin prohibit-password
   ```
   `sshd -t` (валидация) → `systemctl reload ssh` → **обязательно
   проверить новой сессией** (и по ключу, и что парольный вход отдаёт
   `Permission denied (publickey)`) до того, как закрывать текущую.
7. На VPS с малым объёмом RAM (1 ГБ и меньше) — добавить swap **до** первой
   сборки `docker/caddy/Dockerfile`: `xcaddy` компилирует Caddy из
   исходников (`go build`), и на 1 ГБ без swap сборка может не хватить
   памяти. Хватает 2 ГБ:
   ```bash
   fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile \
     && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
   ```

## Операционные нюансы

- **SSH-сессия может обрываться на длинных «тихих» командах** (сборка
  образа без прогресс-вывода в текущий терминал) — какой-то узел по пути
  (NAT/файрвол) считает соединение неактивным и рвёт его (exit 255 у
  ssh-клиента). Сама сборка при этом продолжается на стороне Docker-демона
  независимо от клиента — обрыв SSH её не останавливает. Надёжнее гонять
  долгие сборки полностью отсоединённо от SSH-сессии и опрашивать
  результат короткими подключениями:
  ```bash
  nohup docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    build caddy > /tmp/caddy-build.log 2>&1 & disown
  ```
  затем короткими `ssh ... 'docker images | grep ...'` проверять готовность
  образа, не полагаясь на одну долгоживущую сессию.
- **Диск на маленьком VPS может забиться build-кэшем** — `docker builder
  prune -f` освобождает место без потери уже собранных образов.
- **Не забыть миграции на свежей базе** — первый деплой на чистый Postgres
  без `alembic upgrade head` даёт настоящий `500` (`relation ... does not
  exist`), а не подсказку — это не подразумевается автоматически нигде в
  compose-файлах.

## Процедура

1. VPS + базовая настройка (см. выше).
2. `git clone` репозитория (от имени `deploy`).
3. Скопировать `.env.example` → `.env`. Сгенерировать секреты **на
   VPS** (не копировать с машины разработчика):
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
     run --rm app python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
     run --rm app python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   и вписать результат в `SETTINGS_ENCRYPTION_KEY`/`SESSION_SECRET_KEY`.
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
   (сборка `caddy` — см. "Операционные нюансы" про swap и отсоединённый
   запуск на слабом VPS).
5. **`docker compose -f docker-compose.yml -f docker-compose.prod.yml exec app
   alembic upgrade head`** — легко забыть, но без этого сайт отдаёт `500`
   на первой же настоящей странице.
6. Создать единственного пользователя — **выполняет владелец сам, в своём
   терминале** (пароль не должен проходить через ассистента/чужую сессию):
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec app \
     python -m app.cli create-admin --email you@example.com
   ```
   Пароль забыт — `reset-admin-password` тем же способом (инвалидирует все
   ранее выданные session cookie).
7. Проверить: домен открывается по HTTPS с настоящим сертификатом (не
   self-signed), публичная витрина доступна без входа, вход владельца
   открывает `/admin/*`; `is_public` — публичная обложка отдаёт реальные
   байты анонимному посетителю, приватная — `404` анонимному и `200`
   владельцу через `/admin/editions/{id}` (сама публичная `/catalog/{id}`
   `404`-ит даже владельцу для приватного экземпляра — это дизайн, не
   баг); rate limit на `/login` — несколько быстрых запросов подряд должны
   получить `429`. Отдельно — Service Worker регистрируется на боевом
   домене без ошибок, манифест валиден, «добавить на экран» реально
   работает с телефона (единственная проверка PWA, которую нельзя было
   сделать на шаге 7 без HTTPS).

## Бэкапы

**Сознательно не часть шага 8.** Решение отложено на отдельный шаг после
MVP — куда бэкапить (S3-совместимое хранилище, другой сервер и т.п.), с
какой периодичностью и ротацией, будет спроектировано и реализовано
отдельно. Открытый риск на данный момент: без бэкапов вне VPS база и
особенно фото (обложки — невосстановимы в отличие от БД) не защищены от
потери самого VPS.
