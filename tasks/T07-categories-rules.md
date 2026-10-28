# T07 — Categories + rules engine
Needs: T06
Files: app/rules.py, app/routers/categories.py, app/routers/imports.py, app/main.py, tests/test_rules.py, tests/test_categories_api.py

Do:
1. `rules.py`:
   - `merchant_key(desc)` exactly per SPEC; also wire it into `suggested_keyword` in the transactions API.
   - `match_rule(rules, norm_desc, amount_cents)` → rule or None (winner order per SPEC).
   - `apply_rules(conn, tx_ids=None)` → count updated. Only rows with `category_source='none'`. Sets `rule`.
2. Wire `apply_rules` into the import endpoint (after insert).
3. `routers/categories.py`: GET/POST/PATCH/DELETE categories (DELETE refused with 409 if transactions use it or name is "Uncategorized");
   GET/POST/DELETE `/api/rules`; `POST /api/categorize/run {scope}` → runs `apply_rules` on scoped `none` rows, returns
   `{by_rule, by_llm:0, left, llm_available:false}` (T11 extends it).
4. Tests: `merchant_key("PURCHASE AUTHORIZED ON 09/30 SAMS CLUB #6312 WOODBURY MN P000000244641285 CARD 7673") == "SAMS CLUB"`;
   `merchant_key("KWIK TRIP #178 SOUTH ST PAUL") == "KWIK TRIP"`;
   `merchant_key("PURCHASE INTL AUTHORIZED ON 05/04 PAYMOB-*Samra Aqua CAIRO EGY S356") == "PAYMOB-*SAMRA AQUA"`;
   `merchant_key("ZELLE TO  MAMA ON 09/26 REF # WFCT00TEST01") == "ZELLE TO MAMA"`; `merchant_key("AplPay LYFT 855-280-0278 CA") == "LYFT CA"`;
   SAMS CLUB 38.18 → Transport (amount-bound rule wins), SAMS CLUB 74.65 → Groceries, SAMS CLUB.COM → Shopping (longest keyword),
   `SAM'S CLUB FUEL 6309` → Transport (apostrophe removed, longest keyword);
   `manual` rows are never changed; import of WF fixture categorizes DIRECT DEP as Income and the AMEX payment as Credit Card Payment, `SICK PROD. CENTE 1006822625 …` as Work Reimbursement and `SICK PRODUCTS & PAYROLL …` as Income,
   `Backyard WEB PMTS …` of −1790.00 → Housing, −79.42 → Utilities, −350.00 → Utilities (amount-bound rules, build these rows inline in the test), `INTERNATIONAL PURCHASE TRANSACTION FEE` as Fees, WAY2SAVE transfers as Savings.

Verify: `make test`.
