"""Tests for app.rules.match_rule (T07b)."""
import pytest

from app.rules import match_rule

R_SAMS = [
    {"id": 1, "keyword": "SAMS CLUB", "category_id": 10},
    {"id": 2, "keyword": "SAMS CLUB", "category_id": 20, "max_cents": 6000},
    {"id": 3, "keyword": "SAMS CLUB.COM", "category_id": 30},
    {"id": 4, "keyword": "SAMS CLUB FUEL", "category_id": 40},
]

R_BACKYARD = [
    {"id": 5, "keyword": "BACKYARD WEB", "category_id": 1, "max_cents": 169999},
    {"id": 6, "keyword": "BACKYARD WEB", "category_id": 2, "min_cents": 170000},
]

R_AMAZON = [
    {"id": 7, "keyword": "AMAZON", "category_id": 1},
    {"id": 9, "keyword": "AMAZON", "category_id": 2},
]


@pytest.mark.parametrize(
    ("desc", "amount_cents", "winner"),
    [
        ("SAMS CLUB #6312 WOODBURY", -3818, 2),
        ("SAMS CLUB #6312 WOODBURY", -7465, 1),
        ("SAMS CLUB #1", -6000, 2),
        ("SAMS CLUB #1", -6001, 1),
        ("SAMS CLUB.COM 06279", -72054, 3),
        ("SAMS CLUB FUEL 6309", -2763, 4),
        ("TARGET", -100, None),
    ],
)
def test_sams_cases(desc, amount_cents, winner):
    rule = match_rule(R_SAMS, desc, amount_cents)
    assert rule is None or rule["id"] == winner


@pytest.mark.parametrize(
    ("amount_cents", "winner"),
    [
        (-7942, 5),
        (-179000, 6),
        (-170000, 6),
        (-169999, 5),
    ],
)
def test_backyard_cases(amount_cents, winner):
    rule = match_rule(R_BACKYARD, "BACKYARD WEB PMTS", amount_cents)
    assert rule is not None and rule["id"] == winner


def test_amazon_unbounded_tie_highest_id():
    rule = match_rule(R_AMAZON, "AMAZON MARKETPLACE 112", -5000)
    assert rule is not None and rule["id"] == 9
