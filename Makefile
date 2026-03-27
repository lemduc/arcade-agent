.PHONY: test lint typecheck install dev clean all

all: lint test

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest --tb=short

lint:
	ruff check src/ tests/

typecheck:
	mypy src/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
