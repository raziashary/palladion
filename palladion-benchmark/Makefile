# Thin wrapper over uv; every recipe is a plain `uv run` command, so a machine without make
# can run the same commands by hand. Run from the palladion-benchmark directory.
.PHONY: sync test lint type docs secret-scan check

sync:
	uv sync --locked

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check benchmark tests

type:
	uv run mypy

docs:
	uv run python docs/development/check_docs.py --self-test

secret-scan:
	uv run python -m benchmark.secret_scan --staged

check: sync lint type test docs
