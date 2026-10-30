#!/usr/bin/env bash
# Run on your PC: tests -> commit server repo -> sync -> rebuild on the home server -> health check -> commit.
set -euo pipefail
cd "$(dirname "$0")/.."
source .env.deploy
make test
# Convention: ~/docker is a git repo; .env must be git-ignored; commit before and after deploying.
ssh "$DEPLOY_HOST" "cd ~/docker && git check-ignore -q finances/.env || { echo 'ABORT: finances/.env is not git-ignored'; exit 1; }; git add -A && (git commit -qm 'finances: pre-deploy' || true)"
rsync -az --delete --exclude 'backups' --exclude 'pi-session-*.html' --exclude '.pytest_cache' --exclude 'node_modules' \
  --exclude '.venv' --exclude 'data' --exclude '.git' --exclude '.env' --exclude '.env.deploy' \
  --exclude 'tasks' --exclude 'assets' --exclude '__pycache__' --exclude 'tests' \
  ./ "$DEPLOY_HOST:$DEPLOY_DIR/"
ssh "$DEPLOY_HOST" "cd $DEPLOY_DIR && docker compose up -d --build && sleep 3 && docker compose exec -T finances python -c \"import urllib.request;print(urllib.request.urlopen('http://localhost:8000/api/health').read())\""
ssh "$DEPLOY_HOST" "cd ~/docker && git add -A && (git commit -qm 'finances: deployed' || true)"
echo "Deployed."
