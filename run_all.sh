#!/usr/bin/env bash
# Runs every unchecked task in order; stops at the first one that fails verification.
set -euo pipefail
cd "$(dirname "$0")"
for f in tasks/T*.md; do
  id=$(basename "$f" | cut -d- -f1)
  if grep -qE "^- \[x\] ${id} " PROGRESS.md; then continue; fi
  ./run_task.sh "$id"
  if ! grep -qE "^- \[x\] ${id} " PROGRESS.md; then echo "STOP: $id not ticked in PROGRESS.md"; exit 1; fi
  if [ -f Makefile ] && ! make test >/dev/null 2>&1; then echo "STOP: tests failing after $id"; exit 1; fi
done
echo "All tasks done."
