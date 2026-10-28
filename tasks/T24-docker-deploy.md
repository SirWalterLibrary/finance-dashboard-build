# T24 — Docker, deploy, backup
Needs: T16 (any time after the app runs)
Files: Dockerfile, docker-compose.yml, scripts/deploy.sh, scripts/backup.sh, .env.deploy.example, README.md (short)

Do:
1. Copy from `assets/`: `Dockerfile`, `docker-compose.yml`, `.env.deploy.example`, `scripts/deploy.sh`, `scripts/backup.sh` (keep exec bit).
2. `README.md` (≤40 lines): dev loop (`make setup`, `make seed`, `make dev`, `make test`), deploy (`make deploy`), first-time server setup,
   create users (`docker compose exec finances python scripts/create_user.py <name>`), Nginx Proxy Manager proxy host steps (below), backup.
   NPM: Proxy Host `finances.sirwalterlibrary.ddns.net` → Forward Hostname `finances`, port `8000`, scheme http, request an SSL cert, Force SSL on.
   First-time server: `mkdir -p ~/docker/finances`, copy `.env.example` to `.env` there and edit (`LLM_URL` must point at the Nobara PC, not localhost).
   Server conventions (from the user's homelab doc): stack in `~/docker/finances/`, no `ports` block, `npm_net`, named volume, `restart: always`, `TZ=America/New_York`;
   `~/docker` is a git repo so `deploy.sh` commits before/after and aborts if `finances/.env` is not git-ignored. Do not change these.
3. Confirm `docker build .` works locally if Docker is available (skip otherwise and note it in PROGRESS.md).

Verify: `docker build -t finances-test .` succeeds (or note skipped). `bash -n scripts/*.sh` passes.
USER CHECK: do the first-time server setup, `make deploy`, create two users, open https://finances.sirwalterlibrary.ddns.net, log in.
