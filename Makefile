.PHONY: install test lint typecheck arch check migrate dev clean panel api upgrade

install:
	uv sync --all-extras

test:
	uv run pytest -v

test-fast:
	uv run pytest -x -q

lint:
	uv run ruff check app/ tests/
	uv run ruff format --check app/ tests/

format:
	uv run ruff check --fix app/ tests/
	uv run ruff format app/ tests/

typecheck:
	uv run mypy app/

arch:
	uv run lint-imports

check: lint typecheck arch test

migrate:
	uv run alembic upgrade head

migrate-new:
	uv run alembic revision --autogenerate -m "$(msg)"

dev:
	uv run fastmcp run app/server.py --reload

run:
	uv run fastmcp run app/server.py

api:
	uv run --extra http uvicorn app.api.server:api --host 0.0.0.0 --port 8000 --reload

panel:
	cd panel && bun dev

upgrade:
	uv lock --upgrade && uv sync --all-extras
	cd panel && bun update

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf htmlcov/ .coverage
