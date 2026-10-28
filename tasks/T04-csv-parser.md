# T04 — CSV parser (pure logic)
Needs: T01
Files: app/csvparse.py, tests/test_csvparse.py, tests/fixtures/ (copy of assets/fixtures/*)

Do:
1. Copy `assets/fixtures/*` → `tests/fixtures/`.
2. `csvparse.py`:
   - `norm_desc(s)` uppercase + collapse whitespace.
   - `parse_csv(text, invert) -> (rows, errors)`; `rows` = list of dicts `{date, description, amount_cents, dedupe_key}`; `errors` = list of str (row number + reason).
   - Sniff delimiter (comma or tab). Header required; match DATE/DESCRIPTION/AMOUNT case-insensitively; missing column → error `"missing column X"` and no rows.
   - Date `MM/DD/YYYY` (use `strptime('%m/%d/%Y')`, accepts unpadded too) → ISO.
   - If a STATUS column exists: skip rows whose status is not `posted`; return their count as a 3rd value → signature `parse_csv(text, invert) -> (rows, errors, skipped_pending)`. Amount: strip `$` and `,`, parse with `Decimal`, cents = int(amount*100), then negate if `invert`.
   - Dedupe key per SPEC (occurrence index n for identical date+amount+desc).
   - Bad rows are skipped and reported in `errors`; they never abort the file.
3. Tests using the fixtures: `wf_sample.csv` → 10 rows + 1 pending skipped (the two WM rows have different dedupe_keys; first row description is
   whitespace-collapsed, amount −3818; the eBay row ending in a backslash parses; `SAM'S` normalizes to `SAMS`);
   `amex_sample.csv` with `invert=True` → 720.54 becomes −72054, −704.97 becomes +70497, the two identical DELTA −11.20 rows get different keys,
   the quoted `"PARKWHIZ, INC."` row parses; `tab_sample.tsv` parses 2 rows; missing header column; bad date row reported;
   parsing the same text twice gives identical keys.

Verify: `make test`.
