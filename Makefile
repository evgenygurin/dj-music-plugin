.PHONY: install test test-integration lint typecheck arch check migrate dev clean upgrade

install:
	uv sync --all-extras

# Hermetic gate: live external-service round-trips (-m integration) are
# excluded — they depend on DJ_YM_TOKEN, network, and the shared YM rate
# budget (a running download job trips real 429s). Run them explicitly
# via `make test-integration`.
test:
	uv run pytest -v -m "not integration"

test-integration:
	@echo "Live provider round-trips: needs DJ_YM_TOKEN; pause download jobs or expect 429 flakes."
	uv run pytest -v -m integration

test-fast:
	uv run pytest -x -q -m "not integration"

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
	uv run fastmcp run app/server/__init__.py --reload

run:
	uv run fastmcp run app/server/__init__.py

upgrade:
	uv lock --upgrade && uv sync --all-extras

setup-hooks:
	ln -sf ../../hooks/pre-push .git/hooks/pre-push
	@echo "Git hooks installed"

changelog-draft:
	@echo "=== Commits since last tag ==="
	@git log $$(git describe --tags --abbrev=0)..HEAD --oneline --format="- %s" | sort

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf htmlcov/ .coverage
