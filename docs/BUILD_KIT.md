# Build kit — how this project is built with a local coding agent (Pi)

Goal: a simple joint/personal finance dashboard, built by a local model in small, verified steps, tested on your PC first, then deployed to
`https://finances.sirwalterlibrary.ddns.net`.

## Folder
```
AGENTS.md        rules Pi auto-loads every session
SPEC.md          the single source of truth (data model, API, math)
PROGRESS.md      task checklist + blockers + "User Checks" for you
tasks/T00..T25   one small task each (a fresh session per task)
assets/          ready-made files the tasks copy (schema, seed rules, fixtures, Docker, deploy)
run_task.sh      ./run_task.sh T05   -> one task in a fresh `pi -p` session, then `make test`
run_all.sh       runs unchecked tasks in order; stops at the first failure
```

## How to use
1. Copy this whole folder to your Nobara PC, e.g. `~/projects/finances`, then `cd` into it and `git init`.
2. Make sure Pi works with your Ollama model (`pi` interactive first). Pi auto-loads `AGENTS.md` from the current directory.
3. Run tasks one by one, each in a fresh session. Tasks marked "Self-contained" (T07a onward) use this prompt:
   `Read tasks/T07a-*.md. It is self-contained; do not read SPEC.md. Do exactly that task, following AGENTS.md. Stop when done.`
   Older tasks use `Read SPEC.md and tasks/T0x-*.md. Do exactly that task, following AGENTS.md. Stop when done.`
   Read `PROGRESS.md` after each. The agent commits once per task.
4. After T10 the backend works (curl check). After T16 you can open the app in a browser; every frontend task lists a USER CHECK.
5. If a task fails or the model loops: fix nothing by hand yet — rerun the same task (`git reset --hard` first if it left a mess).
   If it fails twice, split that task file into two smaller ones.
6. T24 sets up Docker + `make deploy`. Server conventions assumed: `~/docker/finances/`, external network `npm_net`, Nginx Proxy Manager.

## Starting Pi
- One-time: `ollama launch pi --config` (sets Ollama as Pi's provider without launching). Then check plain `pi` works: `pi -p "say hi"`.
  If it errors about a provider/model, look at `~/.pi/agent/settings.json` and `~/.pi/agent/models.json`.
- Interactive (always works): `cd` into this folder, run `ollama launch pi --model <your-model>`, then paste:
  `Read SPEC.md and tasks/T00-*.md. Do exactly that task, following AGENTS.md. Stop when done.`
  Exit Pi after each task and relaunch = fresh session. Pi loads `AGENTS.md` from the current directory by itself.
- Scripted: `./run_task.sh T00` calls `pi -p` directly (needs the one-time config above).

## Tuning for a 16 GB card (lessons learned)
- Thinking level: use **low** for coding tasks. At medium, one task spent 78k characters deliberating and compacted its context 9 times without writing a line.
- Context: tasks that compact 7+ times are near the edge. If `ollama ps` still shows 100% GPU, try a larger window; otherwise shrink the task.
- Size tasks by *components*, not lines: one pure function, or one endpoint group, per task. Put every fact the task needs inside the task file.
- When a task changes behaviour that an earlier test asserts, the task file must say which old assertions change.

## Dev vs production
- Dev: `make seed && make dev` → http://localhost:8000, DB `data/dev.db`, fake demo data only (logins demo1 / demo2, password `demo`).
- Prod: `make deploy` runs the tests, syncs code, rebuilds the container. The prod database lives in a Docker volume and is never touched by deploys.
- Real CSV imports happen only on the production site.

## Config
Categorization uses your `d3:9b` system-one endpoint (`LLM_URL`, `LLM_MODEL` in the server `.env`). From the server this must be the Nobara PC address, not localhost.
The app works with the model offline (rules only). Never commit real CSVs — keep them out of this folder.
