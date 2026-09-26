from datetime import date

from sqlalchemy import select

from app import db as app_db
from app import pricing
from app.models import Program


def prog(s, code):
    return s.scalar(select(Program).where(Program.code == code))


def test_seed_counts(client):
    with app_db.SessionLocal() as s:
        progs = s.scalars(select(Program)).all()
        assert len(progs) == 42
        assert sum(len(p.promos) for p in progs) == 81


def test_expected_prices_match_workbook(client):
    d = date(2026, 9, 26)
    with app_db.SessionLocal() as s:
        sf = prog(s, "ZOA | Smart & Final")
        assert pricing.expected_price(sf, "Singles (Frosted Grape/Tropical Punch)", d).price == 1.50
        assert pricing.expected_price(sf, "All", d).price is None          # no base price, no 'All' promo
        assert pricing.expected_price(prog(s, "ZOA | Mountain West North"), "All", d).price == 2.00
        winco = prog(s, "Henry's | WinCo Foods")
        e = pricing.expected_price(winco, "Root Beer", d)
        assert (e.price, e.basis) == (6.49, "Base shelf price")          # 2026 WinCo rows are case cost only
        assert pricing.current_offer_text(winco, d).startswith("Frontline TPR")
        assert pricing.next_promo_start(winco, d) == date(2026, 9, 30)
        harm = prog(s, "Fever-Tree | Harmons")
        assert pricing.expected_price(harm, "4pk", date(2026, 11, 5)).price == 4.99
        assert pricing.expected_price(harm, "4pk", d).price is None
        assert pricing.expected_price(prog(s, "Naked Life | WFM September Feature"), "All", date(2026, 9, 10)).price == 9.49
        ros = prog(s, "Henry's | Rosauers")
        assert pricing.expected_price(ros, "All", date(2025, 9, 1)).price == 5.29  # deep TPR beats TPR


def test_price_check():
    assert pricing.price_check(5.99, 5.99) == "Match"
    assert pricing.price_check(5.99, 6.49) == "Over plan"
    assert pricing.price_check(5.99, 5.49) == "Under plan"
    assert pricing.price_check(None, 5.49) == "No plan price"
    assert pricing.price_check(5.99, None) == ""


def test_sku_prices_for_plan_card(client):
    with app_db.SessionLocal() as s:
        sf = prog(s, "ZOA | Smart & Final")
        assert pricing.active_sku_prices(sf, date(2026, 9, 26)) == [("Singles (Frosted Grape/Tropical Punch)", 1.5, "Singles 2 for $3")]
