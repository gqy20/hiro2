SHELL := /bin/bash

UV ?= uv
PNPM ?= pnpm
WEB_DIR ?= apps/web

.DEFAULT_GOAL := help

.PHONY: help init py-sync web-sync hooks fmt fmt-check lint type test test-py test-web test-e2e test-cov build check verify ci precommit commit-check clean-runs

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
		$(UV) run pytest; \
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
		$(UV) run pytest --cov=backend --cov-report=term-missing --cov-report=xml; \
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
