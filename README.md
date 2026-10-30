# Household Finance Dashboard

Self-hosted, privacy-first budget dashboard: bank CSV imports, local-AI categorization,
joint/personal scopes, budgets, goals and plain forecasting. No cloud, no bank logins.

## Develop
    make setup     # venv + dependencies
    make seed      # demo users demo1/demo2 + demo accounts & transactions (data/dev.db)
    make dev       # run at http://localhost:8000
    make test      # pytest
    make check-js  # node --check on the frontend

## First-time server setup (on the home server)
    mkdir -p ~/docker/finances
    cp .env.example ~/docker/finances/.env     # then edit it
Set `LLM_URL` / `OLLAMA_URL` to the Nobara PC (e.g. `http://192.168.1.12:11434`),
NOT localhost. `.env` must be git-ignored inside the `~/docker` git repo —
`deploy.sh` checks this and aborts the deploy otherwise.
Server conventions: stack lives in `~/docker/finances/`; compose has no `ports` block,
joins the external `npm_net`, named volume `finances_data`, `restart: always`,
`TZ=America/New_York`. `~/docker` is a git repo: `deploy.sh` commits before and after.

## Deploy (from your PC)
    cp .env.deploy.example .env.deploy     # set DEPLOY_HOST / DEPLOY_DIR once
    make deploy        # tests -> git commit -> rsync -> docker compose build+up on the server -> health check -> git commit

## Create users (on the server)
    docker compose exec finances python scripts/create_user.py <name>

## Proxy (Nginx Proxy Manager)
New host: Proxy Host `finances.sirwalterlibrary.ddns.net`, Forward Hostname `finances`,
port `8000`, scheme http; request an SSL certificate and turn Force SSL on.

## Backup (on the server)
    scripts/backup.sh    # consistent DB copy into backups/, keeps the 14 newest (cron it)
