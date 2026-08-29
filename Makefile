SHELL := /bin/bash

UV ?= uv
PNPM ?= pnpm
WEB_DIR ?= apps/web
RUN_DIR ?= .run
API_PORT ?= 8000
WEB_PORT ?= 3000

.DEFAULT_GOAL := help

.PHONY: help init py-sync web-sync hooks fmt fmt-check lint type test test-py test-web test-e2e test-cov build check verify ci precommit commit-check clean-runs db-up db-migrate db-import graph-sync dev stop dev-logs

help:
	@printf '%s\n' "Hiro2 development commands"
	@printf '%s\n' "  make init       Sync uv/pnpm dependencies and install Git hooks"
	@printf '%s\n' "  make check      Run lint, type checks and tests"
	@printf '%s\n' "  make verify     Run formatting checks and all local checks"
	@printf '%s\n' "  make ci         Run the same checks used by GitHub Actions"
	@printf '%s\n' "  make precommit  Run every pre-commit hook on all files"
	@printf '%s\n' "  make commit-check MSG=.git/COMMIT_EDITMSG"
	@printf '%s\n' "  make test-e2e   Run Playwright end-to-end tests"
	@printf '%s\n' "  make build      Build the web application when it exists"
	@printf '%s\n' "  make db-up      Start PostgreSQL and Neo4j with Docker Compose"
	@printf '%s\n' "  make db-migrate Apply pending SQL migrations"
	@printf '%s\n' "  make db-import  Import processed facts into PostgreSQL"
	@printf '%s\n' "  make graph-sync Consume outbox events into Neo4j"
	@printf '%s\n' "  make dev        Start API + Web in the background (idempotent)"
	@printf '%s\n' "  make stop       Stop the background API + Web"
	@printf '%s\n' "  make dev-logs   Tail both background service logs"

init: py-sync web-sync hooks

py-sync:
	$(UV) sync --all-groups

web-sync:
	@if [ -f "$(WEB_DIR)/package.json" ]; then \
		$(PNPM) --dir "$(WEB_DIR)" install --frozen-lockfile; \
	else \
		echo "Skipping pnpm sync: $(WEB_DIR)/package.json not found"; \
	fi

hooks: py-sync
	@if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
		$(UV) run pre-commit install --hook-type pre-commit --install-hooks; \
		$(UV) run pre-commit install --hook-type commit-msg; \
	else \
		echo "Skipping hook install: initialize Git or clone the repository first"; \
	fi

fmt:
	$(UV) run ruff format .
	@if [ -f "$(WEB_DIR)/package.json" ]; then \
		$(PNPM) --dir "$(WEB_DIR)" run format --if-present; \
	fi

fmt-check:
	$(UV) run ruff format --check .
	@if [ -f "$(WEB_DIR)/package.json" ]; then \
		$(PNPM) --dir "$(WEB_DIR)" run format:check; \
	fi

lint:
	$(UV) run ruff check .
	@if [ -f "$(WEB_DIR)/package.json" ]; then \
		$(PNPM) --dir "$(WEB_DIR)" run lint; \
	fi

type:
	@if [ -d backend ]; then \
		$(UV) run mypy backend; \
	else \
		echo "Skipping Python type check: backend/ not found"; \
	fi
	@if [ -f "$(WEB_DIR)/package.json" ]; then \
		$(PNPM) --dir "$(WEB_DIR)" run typecheck; \
	fi

test: test-py test-web test-e2e

test-py:
	@if find tests backend/tests -type f -name 'test_*.py' -print -quit 2>/dev/null | grep -q .; then \
		$(UV) run pytest --cov=backend --cov-report=term-missing --cov-fail-under=60; \
	else \
		echo "Skipping Python tests: no test files yet"; \
	fi

test-web:
	@if [ -f "$(WEB_DIR)/package.json" ]; then \
		$(PNPM) --dir "$(WEB_DIR)" run test; \
	else \
		echo "Skipping web tests: $(WEB_DIR)/package.json not found"; \
	fi

test-e2e:
	@if [ -f "$(WEB_DIR)/playwright.config.ts" ]; then \
		$(PNPM) --dir "$(WEB_DIR)" exec playwright install --with-deps chromium; \
		$(PNPM) --dir "$(WEB_DIR)" run test:e2e; \
	else \
		echo "Skipping e2e: $(WEB_DIR)/playwright.config.ts not found"; \
	fi

test-cov:
	@if find tests backend/tests -type f -name 'test_*.py' -print -quit 2>/dev/null | grep -q .; then \
		$(UV) run pytest --cov=backend --cov-report=term-missing --cov-report=xml --cov-fail-under=60; \
	else \
		echo "Skipping coverage: no Python tests yet"; \
	fi

build:
	@if [ -f "$(WEB_DIR)/package.json" ]; then \
		$(PNPM) --dir "$(WEB_DIR)" run build; \
	else \
		echo "Skipping web build: $(WEB_DIR)/package.json not found"; \
	fi

check: lint type test

smoke:
	$(UV) run scripts/smoke.py

verify: fmt-check check

ci: verify precommit

precommit: py-sync
	@if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
		$(UV) run pre-commit run --all-files; \
	else \
		echo "Skipping pre-commit run: initialize Git or clone the repository first"; \
	fi

commit-check:
	@test -n "$(MSG)" || (echo "Usage: make commit-check MSG=.git/COMMIT_EDITMSG" && exit 2)
	$(UV) run python scripts/cmcheck.py "$(MSG)"

clean-runs:
	@echo "Run artifacts are retained by default; remove a specific run directory manually."

db-up:
	docker compose up -d postgres neo4j

db-migrate:
	@set -a; [ ! -f ./.env ] || . ./.env; set +a; DATABASE_URL="$${DATABASE_URL:-postgresql://hiro2:hiro2@localhost:5433/hiro2}" $(UV) run python scripts/dbmigr.py

db-import:
	@set -a; [ ! -f ./.env ] || . ./.env; set +a; DATABASE_URL="$${DATABASE_URL:-postgresql://hiro2:hiro2@localhost:5433/hiro2}" $(UV) run python scripts/dbimport.py run

graph-sync:
	@set -a; [ ! -f ./.env ] || . ./.env; set +a; DATABASE_URL="$${DATABASE_URL:-postgresql://hiro2:hiro2@localhost:5433/hiro2}" NEO4J_URI="$${NEO4J_URI:-bolt://localhost:7687}" NEO4J_USER="$${NEO4J_USER:-neo4j}" NEO4J_PASSWORD="$${NEO4J_PASSWORD:-hiro2password}" $(UV) run python scripts/outbox.py consume --limit 100

# ponytail: 一键后台启动 API + Web，写 PID 到 .run/，幂等。env 走 .env 或 docker 默认值。
dev:
	@mkdir -p $(RUN_DIR)
	@if [ -f $(RUN_DIR)/api.pid ] && kill -0 $$(cat $(RUN_DIR)/api.pid) 2>/dev/null; then \
		echo "API already running (PID $$(cat $(RUN_DIR)/api.pid))"; \
	else \
		set -a; [ ! -f ./.env ] || . ./.env; set +a; \
		( setsid $(UV) run uvicorn apps.api.main:app --port $(API_PORT) --host 0.0.0.0 </dev/null >$(RUN_DIR)/api.log 2>&1 & echo $$! >$(RUN_DIR)/api.pid ); \
		echo "API started (PID $$(cat $(RUN_DIR)/api.pid)) -> http://localhost:$(API_PORT)"; \
	fi
	@if [ -f $(RUN_DIR)/web.pid ] && kill -0 $$(cat $(RUN_DIR)/web.pid) 2>/dev/null; then \
		echo "Web already running (PID $$(cat $(RUN_DIR)/web.pid))"; \
	else \
		( cd $(WEB_DIR) && setsid env NEXT_PUBLIC_USE_MOCK=false NEXT_PUBLIC_API_BASE_URL=http://localhost:$(API_PORT)/api/v1 \
			$(PNPM) dev </dev/null >$(CURDIR)/$(RUN_DIR)/web.log 2>&1 & echo $$! >$(CURDIR)/$(RUN_DIR)/web.pid ); \
		echo "Web started (PID $$(cat $(CURDIR)/$(RUN_DIR)/web.pid)) -> http://localhost:$(WEB_PORT)"; \
	fi
	@sleep 4
	@printf '\n=== Hiro2 dev status ===\n'
	@printf 'API:    http://localhost:%s\n' "$(API_PORT)"
	@printf 'Web:    http://localhost:%s\n' "$(WEB_PORT)"
	@printf 'Logs:   tail -f %s/{api,web}.log\n' "$(RUN_DIR)"
	@printf 'Stop:   make stop\n'

stop:
	@-pidfile=$(RUN_DIR)/api.pid; \
	if [ -f $$pidfile ]; then \
		pid=$$(cat $$pidfile); \
		if kill -0 $$pid 2>/dev/null; then \
			kill -- -$$pid 2>/dev/null; \
			kill $$pid 2>/dev/null; \
			echo "Stopped api (PID $$pid)"; \
		fi; \
		rm -f $$pidfile; \
	fi; \
	pidfile=$(RUN_DIR)/web.pid; \
	if [ -f $$pidfile ]; then \
		pid=$$(cat $$pidfile); \
		if kill -0 $$pid 2>/dev/null; then \
			kill -- -$$pid 2>/dev/null; \
			kill $$pid 2>/dev/null; \
			echo "Stopped web (PID $$pid)"; \
		fi; \
		rm -f $$pidfile; \
	fi; \
	pgrep -f "uvicorn apps.api.main:app" 2>/dev/null | xargs -r kill 2>/dev/null; \
	pgrep -f "next-server" 2>/dev/null | xargs -r kill 2>/dev/null; \
	pgrep -f "next dev" 2>/dev/null | xargs -r kill 2>/dev/null; \
	true

dev-logs:
	@tail -f $(RUN_DIR)/api.log $(RUN_DIR)/web.log
