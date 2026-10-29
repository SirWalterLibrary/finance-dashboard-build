# T07a — merchant_key (pure function)
Needs: T06. Self-contained: do NOT read SPEC.md.
Files: app/rules.py (new), tests/test_merchant_key.py (new)
Read only: app/csvparse.py (it already has `norm_desc`).

Write `merchant_key(desc: str) -> str` in `app/rules.py`. It suggests a rule keyword from a bank description.
Steps, in this order:
1. `d = norm_desc(desc)`  (import from `app.csvparse`).
2. Remove everything up to and including the first `AUTHORIZED ON dd/dd ` (regex `^.*?AUTHORIZED ON \d\d/\d\d `), if present.
3. Remove a leading `APLPAY `.
4. Split on spaces; drop every token that contains a digit.
5. If `d` starts with `ZELLE TO` or `ZELLE FROM` keep the first 3 tokens, otherwise the first 2. Join with one space.

Write the tests FIRST (`pytest.mark.parametrize`), expected values:
| input | output |
|---|---|
| `PURCHASE                                AUTHORIZED ON   09/30 SAMS CLUB #6312           WOODBURY      MN  P000000244641285   CARD 7673` | `SAMS CLUB` |
| `KWIK TRIP #178 SOUTH ST PAUL` | `KWIK TRIP` |
| `PURCHASE INTL                           AUTHORIZED ON   05/04 PAYMOB-*Samra Aqua        CAIRO         EGY S356124285784368   CARD 3543` | `PAYMOB-*SAMRA AQUA` |
| `ZELLE TO  MAMA ON 09/26 REF # WFCT00TEST01` | `ZELLE TO MAMA` |
| `ZELLE FROM SHEIKH AHMED ON 09/05 REF # WFCT22M7ZSYG DUGSI TUITION` | `ZELLE FROM SHEIKH` |
| `AplPay LYFT         855-280-0278        CA` | `LYFT CA` |
| `SAM'S CLUB FUEL 6309WHITE BEAR LAKE     MN` | `SAMS CLUB` |
| `MONEY TRANSFER                          AUTHORIZED ON   08/12 CASH APP*ABDIRAHMA        Oakland       CA  S306224494194481   CARD 3543` | `CASH APP*ABDIRAHMA` |
| `` (empty) | `` |
| `ATM` | `ATM` |

Verify: `make test`. Touch nothing else.
