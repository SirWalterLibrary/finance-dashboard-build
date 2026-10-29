from pathlib import Path

from app.csvparse import norm_desc, parse_csv

FIX = Path(__file__).parent / "fixtures"


def read(name):
    return (FIX / name).read_text()


def test_wf_fixture():
    rows, errors, skipped_pending = parse_csv(read("wf_sample.csv"), invert=False)
    assert errors == []
    assert len(rows) == 10
    assert skipped_pending == 1
    first = rows[0]
    assert first["date"] == "2026-09-30"
    assert first["amount_cents"] == -3818
    # Whitespace collapsed (multi-space runs become single spaces).
    assert "  " not in first["description"]
    assert first["description"].startswith("PURCHASE AUTHORIZED ON 09/30 SAMS CLUB")
    # The Pending row is absent.
    assert not any("PENDING TEST STORE" in r["description"] for r in rows)
    # eBay row (ends with a backslash) is present and intact.
    ebay = [r for r in rows if r["description"].startswith("eBay")]
    assert len(ebay) == 1
    assert ebay[0]["description"].endswith("\\")
    # Two identical WM SUPERCENTER rows: distinct dedupe keys.
    wps = [r for r in rows if "WM SUPERCENTER" in r["description"]]
    assert len(wps) == 2
    assert wps[0]["dedupe_key"] != wps[1]["dedupe_key"]
    # All dedupe keys unique across the file.
    keys = [r["dedupe_key"] for r in rows]
    assert len(keys) == len(set(keys))


def test_amex_fixture_inverted():
    rows, errors, skipped_pending = parse_csv(read("amex_sample.csv"), invert=True)
    assert errors == []
    assert skipped_pending == 0
    assert len(rows) == 8
    # 720.54 -> -72054, -704.97 -> +70497.
    assert rows[0]["amount_cents"] == -72054
    autopay = [r for r in rows if "AUTOPAY" in r["description"]][0]
    assert autopay["amount_cents"] == 70497
    # Two identical DELTA -11.20 rows: +1120 each, distinct dedupe keys.
    deltas = [r for r in rows if "DELTA AIR LINES ATLANTA" in r["description"]]
    assert len(deltas) == 2
    assert all(r["amount_cents"] == 1120 for r in deltas)
    assert deltas[0]["dedupe_key"] != deltas[1]["dedupe_key"]
    # Quoted comma in description survives.
    parkwhiz = [r for r in rows if r["description"].startswith("PARKWHIZ, INC.")][0]
    assert parkwhiz["description"] == "PARKWHIZ, INC. CHICAGO IL"
    # SAM'S normalizes to SAMS (apostrophe removed).
    sams = [r for r in rows if "CLUB FUEL" in r["description"]]
    assert sams and norm_desc(sams[0]["description"]) == "SAMS CLUB FUEL 6309WHITE BEAR LAKE MN"
    assert norm_desc("SAM'S") == "SAMS"


def test_tab_fixture():
    rows, errors, skipped_pending = parse_csv(read("tab_sample.tsv"), invert=False)
    assert errors == []
    assert skipped_pending == 0
    assert len(rows) == 2
    # Unpadded month/day accepted.
    assert [r["date"] for r in rows] == ["2026-09-29", "2026-09-27"]
    assert [r["amount_cents"] for r in rows] == [72054, 7138]


def test_dedupe_key_deterministic():
    text = read("wf_sample.csv")
    k1 = [r["dedupe_key"] for r in parse_csv(text, False)[0]]
    k2 = [r["dedupe_key"] for r in parse_csv(text, False)[0]]
    assert k1 == k2
    assert len(set(k1)) == len(k1)


def test_missing_header_column():
    rows, errors, _ = parse_csv("DATE,DESCRIPTION\n2026-09-30,FOO\n", invert=False)
    assert rows == []
    assert any("AMOUNT" in e for e in errors)


def test_bad_date_reported_not_fatal():
    text = "DATE,DESCRIPTION,AMOUNT\n99/99/9999,BAD,1.00\n09/30/2025,GOOD,-2.50\n"
    rows, errors, skipped = parse_csv(text, invert=False)
    assert [r["description"] for r in rows] == ["GOOD"]
    assert rows[0]["amount_cents"] == -250
    assert len(errors) == 1
    assert "row" in errors[0].lower()
    assert "date" in errors[0].lower()


def test_odd_amounts_reported_not_fatal():
    text = ("DATE,DESCRIPTION,AMOUNT\n"
            "09/30/2025,NAN,NaN\n"
            "09/30/2025,INF,Infinity\n"
            "09/30/2025,BIG,1e999\n"
            "09/30/2025,GOOD,5.00\n")
    rows, errors, _ = parse_csv(text, invert=False)
    assert [r["description"] for r in rows] == ["GOOD"]
    assert len(errors) == 3
    assert all("amount" in e.lower() for e in errors)


def test_bad_amount_reported_not_fatal():
    text = "DATE,DESCRIPTION,AMOUNT\n09/30/2025,NOPE,abc\n09/30/2025,OK,5.00\n"
    rows, errors, _ = parse_csv(text, invert=False)
    assert [r["description"] for r in rows] == ["OK"]
    assert len(errors) == 1


def test_status_filtering_and_count():
    text = ("DATE,DESCRIPTION,AMOUNT,STATUS\n"
            "09/30/2025,POSTED,-1.00,POSTED\n"
            "09/30/2025,PENDING,2.00,Pending\n"
            "09/30/2025,POSTED2,-3.00,posted\n")
    rows, errors, skipped = parse_csv(text, invert=False)
    assert errors == []
    assert [r["description"] for r in rows] == ["POSTED", "POSTED2"]
    assert skipped == 1


def test_extra_columns_ignored():
    text = ("DATE,DESCRIPTION,AMOUNT,CHECK #,STATUS\n"
            "09/30/2025,FOO,-1.00,123,POSTED\n")
    rows, errors, _ = parse_csv(text, invert=False)
    assert errors == []
    assert rows[0]["date"] == "2025-09-30"


def test_amount_formatting():
    text = "DATE,DESCRIPTION,AMOUNT\n09/30/2025,A,\"$1,234.56\"\n09/30/2025,B,-2.00\n"
    rows, errors, _ = parse_csv(text, invert=False)
    assert errors == []
    assert [r["amount_cents"] for r in rows] == [123456, -200]
    inv_rows, _, _ = parse_csv(text, invert=True)
    assert [r["amount_cents"] for r in inv_rows] == [-123456, 200]


def test_norm_desc_rules():
    assert norm_desc("  sam's   pharmacy ") == "SAMS PHARMACY"
    assert norm_desc("a\tb\nc") == "A B C"
    assert norm_desc("ALREADY-UPPER") == "ALREADY-UPPER"
