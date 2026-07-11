.PHONY: dev down nuke migrate makemigration seed lint format logs logs-ui build

dev: ## Start UI + API + Postgres (one command; migrations auto-apply)
	docker compose up --build

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
