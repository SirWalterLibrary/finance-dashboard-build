"""Forecast math (pure, no FastAPI). Money = integer cents.

All functions take an explicit `today` (datetime.date) — no date.today() here.
No interest of any kind (user policy).
"""
import datetime


def _month(y: int, m: int) -> str:
    m -= 1
    return f"{y + m // 12:04d}-{m % 12 + 1:02d}"


def _yrm(value: str) -> tuple:
    """(year, month) from a YYYY-MM or YYYY-MM-DD date."""
    y, m = value[:7].split("-")
    return int(y), int(m)


def project(start_balance: int, baseline_monthly: int, events, months: int, today) -> dict:
    """Balance projection per SPEC "Math rules".

    month 0 = today's month; balance(m) = start_balance + baseline*m
    + sum of event effects up to month m. Returns
    {points: [{month, balance_cents, events_cents}], first_negative_month}.

    Events: dicts with name/direction("expense"|"income")/kind("one_time"|"recurring")/
    amount_cents (positive)/start_date/end_date/frequency("monthly"|"yearly").
    Recurring applies every month (yearly: every 12 months) from its start
    month through end_date's month (or the horizon). A one-time event
    applies once in its start month (even if that is in the past).
    """
    start_y, start_m = today.year, today.month
    # per-month event effects across the horizon
    per_month = [0] * months
    for ev in events:
        amount = ev["amount_cents"]
        effect = amount if ev["direction"] == "income" else -amount
        sy, sm = _yrm(ev["start_date"])
        start_idx = (sy - start_y) * 12 + (sm - start_m)
        if ev["kind"] == "one_time":
            if 0 <= start_idx < months:
                per_month[start_idx] += effect
            continue
        end_idx = (1 << 30)
        if ev.get("end_date"):
            ey, em = _yrm(ev["end_date"])
            end_idx = (ey - start_y) * 12 + (em - start_m)  # inclusive
        step = 12 if ev.get("frequency") == "yearly" else 1
        for i in range(start_idx, min(end_idx, months - 1) + 1, step):
            if i >= 0:
                per_month[i] += effect
    points = []
    cum = 0
    first_negative = None
    for m in range(months):
        cum += per_month[m]
        balance = start_balance + m * baseline_monthly + cum
        month = _month(start_y, start_m + m)
        if first_negative is None and balance < 0:
            first_negative = month
        points.append({"month": month, "balance_cents": balance,
                       "events_cents": per_month[m]})
    return {"points": points, "first_negative_month": first_negative}
