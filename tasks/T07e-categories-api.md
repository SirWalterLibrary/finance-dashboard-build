# T07e — Categories API
Needs: T07d. Self-contained: do NOT read SPEC.md.
Files: app/routers/categories.py (new), app/main.py (include router), tests/test_categories_api.py (new)
Read only: app/routers/accounts.py (copy its style: `connect()`, `Depends(current_user)`), app/schema.sql (table `categories`), app/main.py.

Endpoints under `/api`, all require login (401 otherwise):
- `GET /categories` -> list of `{id,name,kind,color,description}` ordered by name.
- `POST /categories` body `{name,kind,color?,description?}` -> 201 with the new item. `kind` must be one of `income, expense, transfer, savings, reimbursement`
  (otherwise 422). Blank name -> 422. Duplicate name -> 409.
- `PATCH /categories/{id}` partial body (any of name, kind, color, description) -> updated item. Unknown id -> 404. Duplicate name -> 409.
  Renaming the category named `Uncategorized` -> 409 (code looks it up by name).
- `DELETE /categories/{id}` -> `{"ok": true}`. Unknown id -> 404. 409 if the name is `Uncategorized` or any transaction uses the category.
  Rules that point at it are removed automatically (foreign key cascade).

Tests FIRST: 401 without login; list contains the 21 seeded categories incl. `Uncategorized`; create/patch/delete happy path;
duplicate name 409; bad kind 422; delete `Uncategorized` 409; delete a category used by a transaction 409 (insert one with plain SQL).

Verify: `make test`. Touch nothing else.
