.PHONY: dev down migrate makemigration seed lint format logs build

dev: ## Start API + Postgres with reload (docker compose up)
	docker compose up

down: ## Stop and remove containers
	docker compose down

migrate: ## Apply migrations (alembic upgrade head)
	docker compose exec app alembic upgrade head

makemigration: ## Autogenerate a migration: make makemigration m="message"
	docker compose exec app alembic revision --autogenerate -m "$(m)"

seed: ## Load demo data into the database
	docker compose exec app python seed.py

lint: ## Run Ruff lint
	docker compose exec app ruff check .

format: ## Format with Ruff
	docker compose exec app ruff format .

logs: ## Tail the API logs
	docker compose logs -f app

build: ## Build the production image
	docker compose build
