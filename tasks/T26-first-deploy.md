# T26 — First deploy to the home server (no app code changes)
Needs: T25. Self-contained: do NOT read SPEC.md. Do not read any file except `.env.deploy`, `scripts/deploy.sh` and `PROGRESS.md`.
Files: scripts/deploy.sh (only if Step 1 says so), PROGRESS.md
Rules for this task: you may ONLY touch `~/docker/finances/` and the two lines added to `~/docker/.gitignore` on the server. Never touch other stacks under `~/docker`, never run `docker system prune` or `docker compose down -v`, never print the contents of the server `.env`, never create users (needs a password; the human does that). If any step fails twice, write the exact error under Blockers in PROGRESS.md and stop. Do not improvise.

Step 0 — connection. `.env.deploy` must exist in the project root (it is git-ignored and made by the human). If it does not, write "missing .env.deploy" under Blockers and stop. Otherwise run:
`source .env.deploy && echo "$DEPLOY_HOST" && ssh -o BatchMode=yes "$DEPLOY_HOST" 'echo connected; hostname'`
It must print `connected`. If it asks for a password or fails, Blockers + stop.

Step 1 — deploy script. `grep -c "exclude 'backups'" scripts/deploy.sh` must print 1 or more. If it prints 0, run:
`sed -i "s|^rsync -az --delete \\\\$|rsync -az --delete --exclude 'backups' --exclude 'pi-session-*.html' --exclude '.pytest_cache' --exclude 'node_modules' \\\\|" scripts/deploy.sh && bash -n scripts/deploy.sh`
and check the grep again.

Step 2 — server checks (one ssh call each, show the output):
- `ssh "$DEPLOY_HOST" 'command -v docker rsync git && docker compose version'` -> all must be found.
- `ssh "$DEPLOY_HOST" 'docker network inspect npm_net >/dev/null && echo npm_net-ok'` -> must print `npm_net-ok`.
- `ssh "$DEPLOY_HOST" 'git -C ~/docker rev-parse --is-inside-work-tree'` -> must print `true`.
- `command -v rsync` on this PC must be found.
- `ssh "$DEPLOY_HOST" 'curl -s -m 10 http://192.168.1.12:11434/api/tags | head -c 200'` -> must print JSON (this is the Ollama on the Nobara PC). If it prints nothing, Blockers + stop.

Step 3 — server folder and git ignores:
`ssh "$DEPLOY_HOST" 'mkdir -p ~/docker/finances/backups && cd ~/docker && touch .gitignore && for l in finances/.env finances/backups/; do grep -qxF "$l" .gitignore || echo "$l" >> .gitignore; done && git check-ignore -v finances/.env finances/backups/x'`
Both paths must be listed in the output.

Step 4 — server `.env`, created ONLY if it does not exist yet (never overwrite):
`ssh "$DEPLOY_HOST" '[ -f ~/docker/finances/.env ] && echo ".env already exists, left alone" || { cat > ~/docker/finances/.env <<EOT
LLM_URL=http://192.168.1.12:11434/v1/systemone
LLM_MODEL=d3:9b
LLM_MIN_CONFIDENCE=0
OLLAMA_URL=http://192.168.1.12:11434
EXPLAIN_MODEL=gemma4:26b
COOKIE_SECURE=1
EOT
chmod 600 ~/docker/finances/.env; echo ".env created"; }'`

Step 5 — deploy: `make deploy`. It runs the tests, commits `~/docker` on the server, syncs the files, runs `docker compose up -d --build` and checks `/api/health`. Expected last line: `Deployed.` and a health line containing `ok`.

Step 6 — verify (show the outputs):
- `ssh "$DEPLOY_HOST" 'cd ~/docker/finances && docker compose ps'` -> container `finances` is `Up`.
- `ssh "$DEPLOY_HOST" 'cd ~/docker/finances && docker compose logs --tail 15 finances'` -> no tracebacks.
- `ssh "$DEPLOY_HOST" 'ls ~/docker/finances | head -30'` -> contains `app`, `Dockerfile`, `docker-compose.yml`; must NOT contain `tests`, `tasks`, `.env.deploy`.
- `ssh "$DEPLOY_HOST" 'cd ~/docker && git status --short | head -5'` -> must not list `finances/.env`.

Finish: in PROGRESS.md tick T26 (add the line `- [ ] T26 First deploy` under the task list first if it is missing), add one Log line with the date and the `Deployed.` result, and add these lines under `## User Checks`:
- T26: on the server run `cd ~/docker/finances && docker compose exec finances python scripts/create_user.py <name>` once per person (never run `make seed` on the server).
- T26: in Nginx Proxy Manager add a Proxy Host: finances.sirwalterlibrary.ddns.net, http, forward hostname `finances`, port 8000, SSL certificate + Force SSL; then open https://finances.sirwalterlibrary.ddns.net and log in.
- T26: add a backup cron on the server: `15 3 * * * cd ~/docker/finances && ./scripts/backup.sh`.
Commit and push. Stop.
