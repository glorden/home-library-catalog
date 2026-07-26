.PHONY: dev vendor css-tools css test lint fmt

TAILWIND_VERSION := v3.4.13
HTMX_VERSION := 2.0.4

UNAME_S := $(shell uname -s)
ifneq (,$(findstring MINGW,$(UNAME_S))$(findstring MSYS,$(UNAME_S)))
	TAILWIND_ASSET := tailwindcss-windows-x64.exe
	BIN := bin/tailwindcss.exe
else ifeq ($(UNAME_S),Darwin)
	TAILWIND_ASSET := tailwindcss-macos-x64
	BIN := bin/tailwindcss
else
	TAILWIND_ASSET := tailwindcss-linux-x64
	BIN := bin/tailwindcss
endif

dev:
	docker compose up --build

# Скачивает vendored htmx.min.js (не хранится в git, см. .gitignore)
vendor:
	@mkdir -p app/static/js
	curl -sLo app/static/js/htmx.min.js https://unpkg.com/htmx.org@$(HTMX_VERSION)/dist/htmx.min.js

# Скачивает standalone Tailwind CLI под текущую ОС (не хранится в git, см. .gitignore)
css-tools:
	@mkdir -p bin
	curl -sLo $(BIN) https://github.com/tailwindlabs/tailwindcss/releases/download/$(TAILWIND_VERSION)/$(TAILWIND_ASSET)
	chmod +x $(BIN)

css: css-tools
	$(BIN) -i app/static/css/input.css -o app/static/css/output.css --minify

test:
	pytest

lint:
	ruff check app tests scripts
	ruff format --check app tests scripts

fmt:
	ruff format app tests scripts
