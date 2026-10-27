.PHONY: install data research test lint paper

install:
	pip install -e ".[dev]"
	pre-commit install

data:
	optlab data fetch
	optlab data build
	optlab data check

research:
	optlab research

test:
	pytest

lint:
	ruff check src tests
	ruff format --check src tests
	mypy

paper:
	optlab live run --mode paper
