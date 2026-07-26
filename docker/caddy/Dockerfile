# syntax=docker/dockerfile:1

# rate_limit — не входит в стоковый образ Caddy, добавляется компиляцией
# через xcaddy (см. DEPLOY.md, шаг 8). Билд-стадия, не рантайм-зависимость.
FROM caddy:2-builder AS builder
RUN xcaddy build --with github.com/mholt/caddy-ratelimit

FROM caddy:2-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
