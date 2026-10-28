.PHONY: setup dev test check-js seed deploy
setup:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
dev:
	DB_PATH=data/dev.db .venv/bin/uvicorn app.main:app --reload --host $${HOST:-127.0.0.1} --port 8000
test:
	.venv/bin/python -m pytest -q
check-js:
	@test -d app/static/js || { echo "no js yet"; exit 0; }
	@for f in $$(find app/static -name '*.js' -not -path '*/vendor/*'); do node --check $$f || exit 1; done; echo "js ok"
seed:
	DB_PATH=data/dev.db .venv/bin/python scripts/seed_demo.py
deploy:
	./scripts/deploy.sh
