.PHONY: dev down nuke migrate makemigration seed lint format logs logs-ui build dev-backend-host dev-merchant setup-vision-envs

dev: ## Start UI + API + Postgres (one command; migrations auto-apply)
	docker compose up --build

dev-merchant: ## UI + Postgres in Docker; API on host (merchant Vision pipelines)
	VITE_API_URL=http://localhost:8000/api BACKEND_URL=http://host.docker.internal:8000 docker compose up db ui

setup-vision-envs: ## Install pySceneDetect + VLM virtualenvs for /merchant
	cd Vision/pySceneDetect && python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
	cd Vision/vlm && ./setup_env.sh

dev-backend-host: ## Run FastAPI on the host (use with dev-merchant)
	@test -d backend/.venv || python3 -m venv backend/.venv
	cd backend && .venv/bin/python -m pip install -q -e ".[dev]"
	@echo "Stopping Docker backend so port 8000 is free…"
	@docker compose stop backend 2>/dev/null || true
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

down: ## Stop and remove containers
	docker compose down

nuke: ## Stop everything and wipe the database volume (fresh start)
	docker compose down -v

migrate: ## Apply migrations (alembic upgrade head)
	docker compose exec backend alembic upgrade head

makemigration: ## Autogenerate a migration: make makemigration m="message"
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

seed: ## Load the demo catalogue into the database
	docker compose exec backend python seed.py

lint: ## Lint backend (ruff) and ui (eslint)
	docker compose exec backend ruff check .
	docker compose exec ui pnpm lint

format: ## Format backend (ruff) and ui (prettier)
	docker compose exec backend ruff format .
	docker compose exec ui pnpm format

logs: ## Tail the API logs
	docker compose logs -f backend

logs-ui: ## Tail the UI logs
	docker compose logs -f ui

build: ## Build all images
	docker compose build
