#!/usr/bin/env bash
# Usage: ./run_task.sh T05      -> runs one task in a fresh Pi session, then tests
set -euo pipefail
cd "$(dirname "$0")"
id="${1:?usage: ./run_task.sh T05}"
f=$(ls tasks/${id}-*.md | head -n1)
echo "=== Running $f ==="
{ echo "# SPEC.md"; cat SPEC.md; echo; echo "# TASK FILE: $f"; cat "$f"; } \
  | pi -p "Do exactly the task described above. Follow AGENTS.md. Stop when done."
echo "=== Verifying ==="
if [ -f Makefile ]; then make test; else echo "(no Makefile yet)"; fi
grep -E "^- \[.\] ${id} " PROGRESS.md
