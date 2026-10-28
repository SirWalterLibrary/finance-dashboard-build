#!/usr/bin/env bash
# Run ON THE SERVER (cron-able) from the compose dir: consistent copy of the DB.
set -euo pipefail
mkdir -p backups
docker compose exec -T finances python -c "
import sqlite3
s=sqlite3.connect('/data/finance.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d); d.close()"
docker compose cp finances:/data/backup.db "backups/finance-$(date +%F).db"
ls -t backups/finance-*.db | tail -n +15 | xargs -r rm --
