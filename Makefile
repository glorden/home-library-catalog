.PHONY: dev vendor css-tools css test lint fmt

TAILWIND_VERSION := v3.4.13
BIN := bin/tailwindcss
HTMX_VERSION := 2.0.4

dev:
	docker compose up --build

# Скачивает vendored htmx.min.js (не хранится в git, см. .gitignore)
vendor:
	@mkdir -p app/static/js
	curl -sLo app/static/js/htmx.min.js https://unpkg.com/htmx.org@$(HTMX_VERSION)/dist/htmx.min.js

# Скачивает standalone Tailwind CLI (не хранится в git, см. .gitignore)
css-tools:
	@mkdir -p bin
	curl -sLo $(BIN) https://github.com/tailwindlabs/tailwindcss/releases/download/$(TAILWIND_VERSION)/tailwindcss-linux-x64
	chmod +x $(BIN)

css: css-tools
	$(BIN) -i app/static/css/input.css -o app/static/css/output.css --minify

test:
	pytest

lint:
	ruff check app tests
	ruff format --check app tests

fmt:
	ruff format app tests
