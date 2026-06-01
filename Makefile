# Chainos developer commands. See CLAUDE.md §8.
COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: help up down logs install engine studio terminal seed lint typecheck test fmt schema

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start neo4j/postgres/redis
	$(COMPOSE) up -d

down: ## Stop infra
	$(COMPOSE) down

logs: ## Tail infra logs
	$(COMPOSE) logs -f

install: ## Install JS + Python deps
	pnpm install
	cd services/engine && uv sync --extra dev
	cd services/pipeline && uv sync --extra dev

schema: ## Regenerate the Python graph-schema mirror from the TS spec
	pnpm --filter @chainos/graph-schema gen

engine: ## Run the Engine API (http://localhost:8000)
	cd services/engine && uv run uvicorn app.main:app --reload --port 8000

studio: ## Run Studio admin (http://localhost:3001)
	pnpm --filter @chainos/studio dev

terminal: ## Run Terminal user app (http://localhost:3000)
	pnpm --filter @chainos/terminal dev

seed: ## Build + publish the AI Data Centers seed graph
	cd services/engine && uv run python -m app.seed.load

lint: ## Lint everything
	pnpm lint
	cd services/engine && uv run ruff check app tests

typecheck: ## Typecheck everything
	pnpm typecheck
	cd services/engine && uv run mypy app

test: ## Run all tests
	pnpm test
	cd services/engine && uv run pytest -q

fmt: ## Format
	pnpm exec prettier --write .
	cd services/engine && uv run ruff format app tests
