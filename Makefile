.PHONY: install run test reset
install:
	python -m pip install -e ".[dev]"
run:
	python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

test:
	pytest -q
