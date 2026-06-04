.PHONY: dev test lint format migrate help

# Default target
help:
	@echo "1835 Konsek - Available targets:"
	@echo "  make dev         - Start development environment with docker-compose"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linters (ruff for backend, eslint for frontend)"
	@echo "  make format      - Format code (ruff for backend, prettier for frontend)"
	@echo "  make migrate     - Run database migrations"
	@echo "  make clean       - Clean up docker containers and volumes"
	@echo "  make help        - Show this help message"

dev:
	docker-compose up

dev-build:
	docker-compose up --build

test:
	docker-compose exec backend pytest
	docker-compose exec frontend npm run type-check

lint:
	docker-compose exec backend ruff check .
	docker-compose exec backend mypy . --strict
	docker-compose exec frontend npm run lint

format:
	docker-compose exec backend ruff format .
	docker-compose exec backend ruff check . --fix
	docker-compose exec frontend npm run lint -- --fix

migrate:
	docker-compose exec backend alembic upgrade head

clean:
	docker-compose down -v
