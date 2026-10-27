PY ?= python

.PHONY: install test lint format content check run bench balance web web-serve server-test

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

lint:
	ruff check
	ruff format --check

format:
	ruff format
	ruff check --fix

content:
	$(PY) tools/build_content.py

check: lint test
	git diff --exit-code -- data docs/CONTENT.md

run:
	$(PY) -m lastbean

bench:
	$(PY) tools/bench.py

balance:
	$(PY) tools/balance.py

web:
	$(PY) tools/build_web.py

web-serve:
	$(PY) tools/build_web.py --serve

server-test:
	cd server && $(PY) -m pytest -q
