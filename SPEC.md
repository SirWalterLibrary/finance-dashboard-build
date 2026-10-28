# SPEC — Finance Dashboard (the single source of truth)

## Purpose
Two users (husband, wife) track spending/saving. Joint accounts are visible to both.
Personal accounts are visible only to their owner. Simple UI for a non-technical user.

## Stack (fixed — do not change)
Python 3.11+, FastAPI, SQLite (stdlib `sqlite3`, no ORM), httpx, pytest.
Frontend: plain HTML + CSS + ES modules, Chart.js (vendored file). No build step.
One process serves API (`/api/*`) and static files (`app/static`). Docker for production.

## Layout
```
app/ main.py config.py db.py schema.sql auth.py scope.py csvparse.py rules.py llm.py
     summary.py budgets.py goals.py forecast.py   (pure logic, no FastAPI imports)
     routers/<name>.py                            (thin HTTP layer)
     seed/categories.json seed/rules.json
     static/ index.html css/app.css js/{main,api,fmt}.js js/pages/<page>.js vendor/chart.umd.js
tests/ fixtures/ scripts/ data/(gitignored)
```
Config via env, read at call time (`config.get(name, default)`): `DB_PATH` (default `data/dev.db`),
`LLM_URL` (default `http://localhost:11434/v1/systemone`), `LLM_MODEL` (default `d3:9b`), `LLM_MIN_CONFIDENCE` (default `0`),
`OLLAMA_URL` + `EXPLAIN_MODEL` (optional free-text explain feature only), `COOKIE_SECURE` (default `0`; `1` in production).

## Core definitions
- `amount_cents`: negative = money out, positive = money in, from the account's point of view.
- Credit accounts (AMEX): CSV sign is inverted (positive = purchase). `invert_amounts=1` flips it on import.
- Category `kind`: `income` | `expense` | `transfer` | `savings` | `reimbursement`.
  `reimbursement` = employer deposits repaying work purchases charged to the AMEX (e.g. `SICK PROD. CENTE`). It is NOT income.
- **Gross spending** = −sum(amount_cents) of transactions whose category kind is `expense` (refunds reduce it). `by_category` uses gross.
- **Reimbursed** = sum(amount_cents) of `reimbursement`-kind transactions.
- **Spending** = gross spending − reimbursed (what the cards cost him after work repayments).
  Never count `transfer` (card payments, Cash App, account-to-account) or `savings` as spending. Never count them as income.
- **Income** = sum(amount_cents) where category kind is `income`.
- **Net** = income − spending.
- **Saved** = −sum(amount_cents) of `savings`-kind transactions on non-savings accounts (money moved into savings).
- **Savings balance** = sum over `savings`-type accounts of (opening_balance_cents + sum of their transactions).
- **Uncategorized** is an `expense` category and the default. `category_source`: `none|rule|llm|manual`.

## Scope (privacy — enforced on the SERVER, never trust the client)
`scope` query param: `joint` (default) | `personal` | `combined`.
Account owner: `owner_user_id` NULL = joint, else that user. Owner set of a scope for user U:
joint→{NULL}; personal→{U}; combined→{NULL,U}. Budgets, goals, forecast events use the same `owner_user_id` rule.
Any endpoint touching an account/transaction/goal outside the user's allowed owners returns 404.
Creating budgets/goals/events: scope `personal`→owner=U, `joint`→NULL, `combined` → 400.

## Merchant key + rules
`merchant_key(desc)`: `norm_desc`, then remove everything up to and including `AUTHORIZED ON \d\d/\d\d ` if present
(covers PURCHASE / PURCHASE INTL / PURCHASE RETURN / MONEY TRANSFER / RECURRING PAYMENT…), remove a leading `APLPAY `,
drop any token containing a digit. If the result starts with `ZELLE TO` or `ZELLE FROM`, return the first 3 tokens (includes the name);
otherwise return the first 2 tokens joined by a space. This is only a SUGGESTION shown to the user (editable).
Rule = keyword (uppercase substring of normalized description) + category + optional `min_cents`/`max_cents`
(compared to ABS(amount)). Winner: longest keyword; tie → rule with an amount bound; tie → newest.
Rules only touch transactions with `category_source='none'`. `manual` is never overwritten.

## Import dedupe
`dedupe_key = sha1(f"{date}|{amount_cents}|{norm_desc}|{n}")` where n = occurrence index (0,1,2…) of identical
(date, amount, norm_desc) within the file. UNIQUE(account_id, dedupe_key). Re-importing a file adds 0 rows.
`norm_desc` = description uppercased, apostrophes removed, whitespace collapsed (so `SAM'S` = `SAMS`).
CSV (real exports): Wells Fargo = quoted, header `DATE,DESCRIPTION,AMOUNT,CHECK #,STATUS`; AMEX = header `Date,Description,Amount`.
Dates `MM/DD/YYYY` (zero-padded or not). Delimiter comma or tab; header row required; columns matched case-insensitively;
extra columns ignored. If a STATUS column exists, import only rows whose status is `posted` (case-insensitive); count the rest as `skipped_pending`.
Strip `$` and `,` from amounts; parse with `Decimal`. Descriptions may end with a backslash — keep as is (standard `csv` module handles it).

## API (all JSON; all except /api/login and /api/health need a session cookie)
```
POST /api/login {username,password} → 200 sets cookie `sid` (HttpOnly, SameSite=Lax) | 401
POST /api/logout ; GET /api/me → {id,username}
GET  /api/accounts?scope=            → [{id,name,institution,type,shared,balance_cents,tx_count}]
POST /api/accounts {name,institution,type:checking|savings|credit,shared:bool,opening_balance_cents?}
PUT  /api/accounts/{id}/balance {current_balance_cents}  → server sets opening_balance so today's balance = the given value (CSV has no balances)
DELETE /api/accounts/{id}            (deletes its transactions)
POST /api/accounts/{id}/import       multipart `file` → {added,skipped_duplicates,skipped_pending,errors:[str]}
GET  /api/transactions?scope=&account_id=&category_id=&q=&direction=in|out&source=none|rule|llm|manual&from=&to=&limit=50&offset=0
                                     → {items:[{id,date,description,amount_cents,account_id,account_name,category_id,category_name,category_color,category_source,category_confidence,suggested_keyword}],total}
PATCH /api/transactions/{id} {category_id, apply_to_similar?:bool, keyword?:str}
DELETE /api/transactions/{id}
GET/POST/PATCH/DELETE /api/categories   {name,kind,color,description}
GET/POST/DELETE /api/rules              {keyword,category_id,min_cents?,max_cents?}
POST /api/categorize/run {scope}        → {by_rule,by_llm,left,llm_available}   (`left` = rows still source `none`)
GET  /api/summary?scope=&from=&to=      → {income_cents,spending_cents,reimbursed_cents,net_cents,saved_cents,tx_count,uncategorized_count,
                                           by_category:[{category_id,name,color,cents,pct}],
                                           by_month:[{month:"YYYY-MM",income_cents,spending_cents,reimbursed_cents,by_category:{name:cents}}]}
                                           (spending = gross − reimbursed; by_category sums to gross)
GET  /api/budgets?scope=&month=YYYY-MM → [{id|null,category_id,name,color,limit_cents,spent_cents,pct,status:"ok"|"warn"|"over"}]
PUT  /api/budgets {scope,category_id,limit_cents}   ; DELETE /api/budgets/{id}
GET/POST/PATCH/DELETE /api/goals        {name,target_cents,target_date?,allocated_cents,scope(on create)}
GET  /api/savings?scope=               → {balance_cents,allocated_cents,unallocated_cents}
GET  /api/goals/simulate?scope=&months=6&monthly_cents=
                                       → {monthly_cents_used,goals:[{id,remaining_cents,months_needed|null,eta_date|null,on_track|null}]}
GET/POST/PATCH/DELETE /api/forecast/events {name,group_name?,direction:"expense"|"income",kind:"one_time"|"recurring",
                                       amount_cents,start_date,end_date?,frequency?:"monthly"|"yearly",scope(on create)}
GET  /api/forecast/projection?scope=&months=120&monthly_cents=&start_balance_cents=
                                       → {baseline_monthly_cents,start_balance_cents,points:[{month,balance_cents,events_cents}],first_negative_month|null}
POST /api/explain {kind:"goals"|"forecast",scope} → {text,llm_available}   (optional feature)
```
Budget status: pct<80 ok, 80–100 warn, >100 over. Budget pct = spent/limit*100 (rounded int).

## Math rules (done in code, NEVER by the LLM)
- Baseline monthly saving = average monthly Net over the last `months` COMPLETE calendar months in scope
  (or `monthly_cents` override). Minimum 0 months of data → 0.
- Goal ETA: remaining = max(target − allocated, 0); if remaining=0 → eta today; if monthly ≤ 0 → null;
  else months_needed = ceil(remaining/monthly); eta = first day of month (today + months_needed months).
  `on_track` = eta ≤ target_date (null if no target_date or no eta).
- Projection: month 0 = current month. balance(m) = start_balance + baseline×m + Σ event effects up to m.
  Default start_balance = Savings balance in scope. **No interest/APY anywhere** (user policy).
- Recurring event: applies every month (or every 12 months from start) from start_date through end_date (or horizon).
  One-time: applies once in start_date's month. expense = negative effect, income = positive.

## LLM rules (categorizer = the user's local "system one" model `d3:9b` through Ollama)
The user's working script defines the API. Copy its shape exactly; one request per transaction:
```
POST {LLM_URL}   (timeout 30 s)
{"model": LLM_MODEL,
 "state": "Transaction Description: <desc> | Amount: $<signed dollars, negative = money out>",
 "questions": {"category": {"type":"choice",
     "instructions":"Which financial category best fits this transaction?",
     "criteria": {<category name>: <category description from DB>, ...}}}}
→ {"answers":{"category":{"choice":"<name>","confidence":0.93}}}
```
- `criteria` is built from the `categories` table (name → description), so editing a description changes the model's behaviour.
- Reinforcement: append up to 5 `merchant_key` examples per category (from `manual` corrections) to that category's criteria text: `"<description> Examples: KWIK TRIP, ..."`.
- Cache within one run by `(merchant_key, sign)`: classify once, apply to all identical rows (many merchants repeat).
- Accept the answer only if `choice` is an existing category name and `confidence >= LLM_MIN_CONFIDENCE`; store `category_confidence`; source `llm`.
- Any error/timeout/bad JSON on the FIRST call → `llm_available:false`, change nothing. Errors later → leave that row `none` and continue.
- The LLM never changes `manual` rows and never does arithmetic or dates.
- Optional free-text explanations (T15) use standard Ollama `POST {OLLAMA_URL}/api/chat` with `EXPLAIN_MODEL` — NOT the system-one endpoint.
