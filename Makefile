.PHONY: install format lint test typecheck build publish clean

install:
	uv sync

format:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run mypy src

test:
	uv run pytest -q

build:
	uv build

publish: build
	uv publish

clean:
	rm -rf dist/
	rm -rf build/
	rm -rf .ruff_cache/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
