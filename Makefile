# ESG / Carbon Accounting platform — developer commands.
SHELL := /bin/bash
ENGINE := cd engine &&
WEB := cd web &&

.PHONY: help up down env reset refdata bootstrap demo engine web dev test test-unit test-db e2e lint format typecheck

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

up: ## Start local Supabase (Docker Desktop must be running)
	supabase start
	./scripts/gen-env.sh

down: ## Stop local Supabase
	supabase stop

env: ## Regenerate engine/.env and web/.env.local from the running stack
	./scripts/gen-env.sh

reset: ## Recreate the DB from migrations, load reference data, create dev users
	supabase db reset
	$(MAKE) refdata bootstrap

refdata: ## Load cited reference data from reference-data/
	$(ENGINE) uv run python -m app.refdata.load

bootstrap: ## Create local dev users and demo companies
	$(ENGINE) uv run python -m scripts.bootstrap_dev

demo: ## Load demo customer data (two demo projects for Sample Textiles Ltd)
	$(ENGINE) uv run python -m scripts.demo_data

engine: ## Run the engine API on :8000
	$(ENGINE) uv run uvicorn app.main:app --port 8000 --reload

web: ## Run the web app on :3000
	$(WEB) npm run dev

test: test-unit test-db ## All engine tests

test-unit: ## Engine unit tests (no database)
	$(ENGINE) uv run pytest -m "not db" -q

test-db: ## DB / RLS / API integration tests (needs `make up` + `make engine`)
	$(ENGINE) uv run pytest -m db -q

e2e: ## Playwright golden path (needs engine + web running)
	$(WEB) npx playwright test

lint: ## Lint engine and web
	$(ENGINE) uv run ruff check app tests scripts
	$(WEB) npm run lint

format: ## Format engine code
	$(ENGINE) uv run ruff format app tests scripts

typecheck: ## Type-check the web app
	$(WEB) npx tsc --noEmit
