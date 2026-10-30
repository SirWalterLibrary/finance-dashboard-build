"""LLM categorizer (SPEC "LLM rules").

Asks the system-one model (d3:9b) to pick a category for the
transactions no rule matched. The request/response shape mirrors the
user's existing script: model, state, questions.category with
type/instructions/criteria, and answers.category.{choice,confidence}.
"""
import httpx

from app import config
from app.rules import merchant_key

STATE_NOTE = ("You have already reviewed the merchant names below in an "
              "earlier conversation turn. Do not ask the user for help or "
              "clarification: just pick the best category for each one.")


def _min_confidence() -> float:
    try:
        return float(config.get("LLM_MIN_CONFIDENCE", "0.8"))
    except ValueError:
        return 0.8


def classify(description, amount_cents, criteria):
    """Ask the LLM for a category. Returns (category|None, confidence|None).

    Any transport/HTTP/JSON problem, or a missing key in the answer,
    yields (None, None) — never an exception.
    """
    sign = "out" if amount_cents < 0 else "in"
    payload = {
        "model": config.get("LLM_MODEL"),
        "state": STATE_NOTE,
        "questions": {
            "category": {
                "type": "single-select",
                "instructions": (
                    "Pick the single best category for this bank "
                    f"transaction: {description!r} ({abs(amount_cents)} "
                    f"cents {sign}) from the account."
                ),
                "criteria": criteria,
            }
        },
    }
    try:
        resp = httpx.post(config.get("LLM_URL"), json=payload, timeout=30)
        resp.raise_for_status()
        answer = resp.json()["answers"]["category"]
        choice = answer["choice"]
        confidence = float(answer["confidence"])
    except Exception:
        return None, None
    return choice, confidence


def build_criteria(conn):
    """Return {category_name: "description — Examples: A, B"}.

    Examples come from up to 5 most recent distinct merchant_keys of
    manually-categorized ('manual') rows in that category, oldest to
    newest. Categories without manual rows keep their plain description.
    """
    criteria = {
        r["name"]: r["description"]
        for r in conn.execute("SELECT name, description FROM categories")
    }
    rows = conn.execute(
        "SELECT t.category_id, t.description FROM transactions t "
        "WHERE t.category_source = 'manual' ORDER BY t.id DESC"
    ).fetchall()
    cat_names = {
        r["id"]: r["name"]
        for r in conn.execute("SELECT id, name FROM categories")
    }
    seen = {}
    for r in rows:
        name = cat_names.get(r["category_id"])
        if name not in criteria:
            continue
        keys = seen.setdefault(name, [])
        mk = merchant_key(r["description"])
        if mk and mk not in keys:
            keys.append(mk)
    for name, keys in seen.items():
        if keys:
            criteria[name] = (
                f"{criteria[name]} — Examples: {', '.join(keys[:5])}"
            )
    return criteria


def categorize_pending(conn, tx_rows):
    """Run the LLM over the 'none' rows left after the rule pass.

    tx_rows: rows in the requested scope still with category_source
    'none'. Rows are grouped by (merchant_key, sign); `classify` is
    called once per group with the first row as the representative.
    The first call returning (None, None) means the model is
    unavailable: nothing is changed and the function stops. A later
    failure only skips that group. An answer is applied only when the
    choice is an existing category and its confidence is at least
    LLM_MIN_CONFIDENCE. Returns {"by_llm": n, "llm_available": bool} where
    llm_available is True only if the first classify call answered.
    """
    result = {"by_llm": 0, "llm_available": False}
    if not tx_rows:
        return result
    criteria = build_criteria(conn)
    by_name = {c["name"]: c["id"] for c in
               conn.execute("SELECT id, name FROM categories")}

    groups = {}
    for r in tx_rows:
        key = (merchant_key(r["description"]), r["amount_cents"] < 0)
        groups.setdefault(key, []).append(r)

    first_call = True
    for rows in groups.values():
        rep = rows[0]
        choice, confidence = classify(
            rep["description"], rep["amount_cents"], criteria
        )
        if choice is None or confidence is None:
            if first_call:
                return result  # model unavailable: change nothing
            continue  # later failure: skip this group only
        first_call = False
        result["llm_available"] = True
        cat_id = by_name.get(choice)
        if cat_id is None or confidence < _min_confidence():
            continue
        with conn:
            for r in rows:
                conn.execute(
                    "UPDATE transactions SET category_id = ?, "
                    "category_source = 'llm', category_confidence = ? "
                    "WHERE id = ? AND category_source = 'none'",
                    (cat_id, confidence, r["id"]),
                )
        result["by_llm"] += len(rows)
    return result
