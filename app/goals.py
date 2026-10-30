"""Goals math (pure, no FastAPI). Money = integer cents.

All functions take an explicit `today` (datetime.date) — no date.today() here.
"""
import datetime
import math


def savings_summary(balance_cents: int, allocated_list) -> dict:
    """{balance_cents, allocated_cents, unallocated_cents} (SPEC "Goals")."""
    allocated = sum(allocated_list)
    return {
        "balance_cents": balance_cents,
        "allocated_cents": allocated,
        "unallocated_cents": balance_cents - allocated,
    }


def baseline_monthly(by_month, months: int, today) -> int:
    """Average monthly net over the last `months` COMPLETE calendar months.

    by_month: list of {"month": "YYYY-MM", "income_cents", "spending_cents"}.
    The current month (today's month) is excluded even if present.
    Minimum 0 months of data -> 0.
    """
    current = today.strftime("%Y-%m")
    nets = [
        m["income_cents"] - m["spending_cents"]
        for m in sorted(by_month, key=lambda m: m["month"])
        if m["month"] != current
    ]
    if not nets:
        return 0
    return max(sum(nets[-months:]) // len(nets[-months:]), 0)


def eta(remaining_cents: int, monthly_cents: int, today):
    """(eta_date, months_needed) per SPEC "Math rules", or None if no ETA.

    remaining <= 0 -> (today, 0); monthly <= 0 -> None;
    else months_needed = ceil(remaining/monthly), eta = first day of the
    month (today + months_needed months).
    """
    if remaining_cents <= 0:
        return today, 0
    if monthly_cents <= 0:
        return None
    months_needed = math.ceil(remaining_cents / monthly_cents)
    m = today.month - 1 + months_needed
    y = today.year + m // 12
    return datetime.date(y, m % 12 + 1, 1), months_needed


def on_track(eta_date, target_date):
    """True/False, or None if either date is missing (SPEC "Math rules")."""
    if eta_date is None or target_date is None:
        return None
    return eta_date <= target_date
