# syntax=docker/dockerfile:1

# --- assets: скачать Tailwind CLI и htmx.min.js, собрать CSS ---
FROM debian:bookworm-slim AS assets
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /assets
COPY tailwind.config.js .
COPY app/static/css/input.css app/static/css/input.css
COPY app/templates app/templates
RUN curl -sLo tailwindcss \
      https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x tailwindcss \
    && ./tailwindcss -i app/static/css/input.css -o app/static/css/output.css --minify
RUN curl -sLo app/static/js/htmx.min.js \
      https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js

# --- runtime ---
FROM python:3.12-slim AS runtime
WORKDIR /code
COPY pyproject.toml .
COPY app app
RUN pip install --no-cache-dir .
COPY --from=assets /assets/app/static/css/output.css app/static/css/output.css
COPY --from=assets /assets/app/static/js/htmx.min.js app/static/js/htmx.min.js
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
