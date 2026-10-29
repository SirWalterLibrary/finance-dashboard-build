# T07a-fix — make the suite green again (one line)
Self-contained: do NOT read SPEC.md.
Files: app/routers/imports.py, PROGRESS.md
Read only: app/routers/imports.py.

Problem: since T07a created app/rules.py, imports.py calls `rules.apply_rules(...)`, which does not exist until T07c. Two tests in tests/test_import_api.py fail with AttributeError.

Change exactly this line in `import_file`:
    if tx_ids and rules is not None:
to:
    if tx_ids and rules is not None and hasattr(rules, "apply_rules"):

Do not add apply_rules. Do not touch tests. (T07d later replaces this guard with a plain import.)

Then in PROGRESS.md: change the Blockers section back to `(none)`, and add one Log line: "T07a-fix: hasattr guard in imports.py; suite green".
Verify: `make test` must show 60 passed, 0 failed. Commit.
