# T07b — match_rule (pure function)
Needs: T07a. Self-contained: do NOT read SPEC.md.
Files: app/rules.py (add one function), tests/test_match_rule.py (new)
Read only: app/rules.py.

Add `match_rule(rules, norm_description, amount_cents)` to `app/rules.py`. No database, no imports beyond the standard library.
- `rules` = list of dicts: `id`, `keyword` (already normalized, uppercase), `category_id`, `min_cents` (None or int), `max_cents` (None or int).
- A rule matches when `keyword in norm_description` AND the amount bound holds: with `a = abs(amount_cents)`,
  `min_cents is None or a >= min_cents` and `max_cents is None or a <= max_cents` (both inclusive).
- Winner among matching rules: longest keyword; tie -> a rule that has any bound (min or max not None); tie -> highest `id`.
- Return the winning rule dict, or `None`.

Write the tests FIRST. Use these hand-made rules:
`R=[{id:1,keyword:"SAMS CLUB",category_id:10}, {id:2,keyword:"SAMS CLUB",category_id:20,max_cents:6000},
{id:3,keyword:"SAMS CLUB.COM",category_id:30}, {id:4,keyword:"SAMS CLUB FUEL",category_id:40}]`
| norm description | amount_cents | winner id |
|---|---|---|
| `SAMS CLUB #6312 WOODBURY` | -3818 | 2 |
| `SAMS CLUB #6312 WOODBURY` | -7465 | 1 |
| `SAMS CLUB #1` | -6000 | 2 |
| `SAMS CLUB #1` | -6001 | 1 |
| `SAMS CLUB.COM 06279` | -72054 | 3 |
| `SAMS CLUB FUEL 6309` | -2763 | 4 |
| `TARGET` | -100 | None |
Second set: `[{id:5,keyword:"BACKYARD WEB",category_id:1,max_cents:169999},{id:6,keyword:"BACKYARD WEB",category_id:2,min_cents:170000}]`
with description `BACKYARD WEB PMTS`: -7942 -> 5, -179000 -> 6, -170000 -> 6, -169999 -> 5.
Third set: two unbounded `AMAZON` rules with ids 7 and 9 -> id 9 wins.

Verify: `make test`. Touch nothing else.
