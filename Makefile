.PHONY: install install-frontend seed run frontend test lint

install:
	pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

# Preload the fixed corpus in data/seed_corpus/ (idempotent; safe to re-run)
seed:
	python -m scripts.seed

# Run the API (terminal 1)
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run the React chat UI (terminal 2) — proxies API calls to :8000
frontend:
	cd frontend && npm run dev

test:
	pytest -q

lint:
	ruff check app tests
