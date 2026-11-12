# NOVA Commerce: one command from the repository root.
# Supported development hosts: macOS and Linux with GNU Make, Python, and Node.js.
.DEFAULT_GOAL := dev
SHELL := /bin/bash
PYTHON ?= python3
NPM ?= npm
VENV := backend/.venv
PY := $(VENV)/bin/python
PIP := $(PY) -m pip
PY_STAMP := $(VENV)/.dependencies-installed
JS_STAMP := frontend/node_modules/.dependencies-installed
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: help dev setup install configure deps frontend-deps backend frontend test test-backend test-ai build check verify start reset-db clean clean-all doctor validate-deps check-ai-config

help:
	@echo 'NOVA Commerce — commands (run from project root):'
	@echo '  make              Install missing dependencies and run both apps'
	@echo '  make dev          Same as make (frontend :5173, API :8000)'
	@echo '  make setup        Initialize local .env and install Python/Node dependencies'
	@echo '  make configure    Create backend/.env from the template if missing'
	@echo '  make test         Run backend tests and A2UI protocol adapter tests'
	@echo '  make test-ai      Call real OpenAI via PydanticAI (uses API credit)'
	@echo '  make build        Validate Python and build React frontend'
	@echo '  make check        Run tests and React production build'
	@echo '  make start        Build and run frontend+API on port 8000'
	@echo '  make reset-db     Reset demo DB/catalog/orders (destructive)'
	@echo '  make clean        Delete build outputs and caches (keep DB)'
	@echo '  make clean-all    Clean and delete installed dependencies'
	@echo '  make doctor       Check Python, Node, npm, make versions'
	@echo '  make validate-deps Check React/Tailwind/daisyUI major versions'
	@echo '  make check-ai-config Check presence of OpenAI API key (no API call)'

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)

$(PY_STAMP): backend/requirements.txt | $(VENV)/bin/python
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	@touch $(PY_STAMP)

validate-deps:
	@$(PYTHON) scripts/check_frontend_deps.py

$(JS_STAMP): frontend/package.json scripts/check_frontend_deps.py
	@$(PYTHON) scripts/check_frontend_deps.py
	@if [[ -f frontend/package-lock.json ]]; then \
		cd frontend && $(NPM) ci --no-audit --no-fund --strict-peer-deps; \
	else \
		cd frontend && $(NPM) install --no-audit --no-fund --strict-peer-deps; \
	fi
	cd frontend && $(NPM) ls react react-dom tailwindcss daisyui
	@touch $(JS_STAMP)

check-ai-config:
	@$(PYTHON) scripts/check_ai_config.py

configure:
	@if [[ ! -f backend/.env ]]; then cp backend/.env.example backend/.env; echo 'Created backend/.env. Add your OPENAI_API_KEY before chatting.'; fi

deps: $(PY_STAMP) $(JS_STAMP)

frontend-deps: $(JS_STAMP)

setup: configure
	@$(MAKE) --no-print-directory deps

install: setup

# The script traps SIGINT/SIGTERM and shuts down both servers.
dev: configure check-ai-config deps
	@bash scripts/dev.sh "$(PY)" "$(NPM)"

backend: $(PY_STAMP)
	$(PY) -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend/app --host 127.0.0.1 --port 8000

frontend: $(JS_STAMP)
	cd frontend && $(NPM) run dev

test-backend: $(PY_STAMP)
	cd backend && .venv/bin/python -m pytest -q

test: test-backend validate-deps frontend-deps
	cd frontend && $(NPM) run test

test-ai: $(PY_STAMP)
	$(PY) scripts/test_ai.py

build: deps
	cd frontend && $(NPM) ls react react-dom tailwindcss daisyui
	$(PY) -c 'import ast,pathlib; [ast.parse(p.read_text(encoding="utf-8"),filename=str(p)) for p in pathlib.Path("backend").rglob("*.py") if ".venv" not in p.parts]; print("Python syntax OK")'
	cd frontend && $(NPM) run build

check: test build

verify: check

# Production-like single-port run; browser opens http://localhost:8000.
start: configure check-ai-config build
	$(PY) -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

reset-db: $(PY_STAMP)
	@echo 'Resetting demo SQLite (all carts, orders and payments will be removed)...'
	$(PY) scripts/reset_db.py

clean:
	rm -rf frontend/dist backend/.pytest_cache .pytest_cache
	find backend -type d -name __pycache__ -prune -exec rm -rf {} +

clean-all: clean
	rm -rf frontend/node_modules backend/.venv

doctor:
	@echo 'make:'; $(MAKE) --version | head -1
	@echo 'Python:'; $(PYTHON) --version
	@echo 'Node:'; node --version
	@echo 'npm:'; $(NPM) --version
