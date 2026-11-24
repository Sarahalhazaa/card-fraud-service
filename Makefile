# Every command of the project, in one place. Run them from the project folder with .venv active.
.PHONY: front install reference train golden score run lint lock image up down smoke

install:      ## install the project and the dev tools into the active venv
	python -m pip install -e ".[dev]"

reference:    ## run the notebook's own code once and save its answers in golden/
	python legacy/notebook_reference.py

train:        ## train with the new code and save artifacts/
	python -m card_fraud.train

golden:       ## prove the new code gives the notebook's answers
	python scripts/check_golden.py

score:        ## score one payment from the command line (no API)
	python -m card_fraud.score_one payloads/notebook_fraud.json

run:          ## start the API on http://localhost:8000/docs
	python -m uvicorn card_fraud.api.app:create_app --factory --reload

front:        ## start the front end on http://localhost:5173 (the API must be running)
	cd frontend && npm install && npm run dev

lint:
	ruff check src scripts legacy

lock:         ## pin every library for the Linux container (Python 3.12)
	uv pip compile pyproject.toml --python-version 3.12 --python-platform linux --no-annotate --no-header -o requirements.lock

image:
	docker build --build-arg GIT_SHA=$$(git rev-parse --short HEAD) -t card-fraud-service:dev .

up:
	docker compose up --build -d

down:
	docker compose down

smoke:        ## the running service answers: ready, then one real request
	curl -fsS localhost:8000/v1/ready && echo
	curl -fsS localhost:8000/v1/score -H "content-type: application/json" -d @payloads/notebook_fraud.json && echo
