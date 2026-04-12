.PHONY: dev dev-down test lint typecheck db-migrate db-revision clean

# --- Development ---
dev:
	docker compose up -d

dev-down:
	docker compose down

dev-logs:
	docker compose logs -f

# --- Testing ---
test: test-web test-api test-billing

test-web:
	cd apps/web && pnpm test

test-api:
	cd services/api-gateway && python -m pytest -v

test-billing:
	cd services/billing-service && go test ./...

# --- Linting ---
lint: lint-web lint-api lint-go

lint-web:
	cd apps/web && pnpm lint

lint-api:
	cd services/api-gateway && ruff check . && ruff format --check .

lint-go:
	cd services/billing-service && golangci-lint run
	cd services/sync-service && golangci-lint run

# --- Type Checking ---
typecheck: typecheck-web typecheck-api

typecheck-web:
	cd apps/web && pnpm typecheck

typecheck-api:
	cd services/api-gateway && mypy app

# --- Database ---
db-migrate:
	cd services/api-gateway && alembic upgrade head

db-revision:
	cd services/api-gateway && alembic revision --autogenerate -m "$(msg)"

db-downgrade:
	cd services/api-gateway && alembic downgrade -1

# --- Clean ---
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
