.PHONY: install test lint typecheck check migrate dev clean

install:
	uv sync --all-extras

test:
	uv run pytest -v

lint:
	uv run ruff check app/ tests/
	uv run ruff format --check app/ tests/

format:
	uv run ruff check --fix app/ tests/
	uv run ruff format app/ tests/

typecheck:
	uv run mypy app/

check: lint typecheck test

migrate:
	uv run alembic upgrade head

migrate-new:
	uv run alembic revision --autogenerate -m "$(msg)"

dev:
	uv run fastmcp dev app/server.py --reload

run:
	uv run fastmcp run app/server.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf htmlcov/ .coverage
