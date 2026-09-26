"""Promo status and expected shelf price - same rules as the Excel workbook.

Expected price for a program + SKU on a date:
  1. lowest active promo with a unit retail for that exact SKU, else
  2. lowest active promo with a unit retail for SKU "All", else
  3. the program's base shelf price, else None ("Not set").
"""
from dataclasses import dataclass
from datetime import date

from .models import Program, Promo


def promo_status(p: Promo, day: date) -> str:
    if day < p.start:
        return "Upcoming"
    if day > p.end:
        return "Expired"
    return "Active"


def active_promos(program: Program, day: date) -> list[Promo]:
    return [p for p in program.promos if p.start <= day <= p.end]


@dataclass
class Expected:
    price: float | None
    basis: str


def expected_price(program: Program, sku: str | None, day: date) -> Expected:
    sku = (sku or "All").strip() or "All"
    active = [p for p in active_promos(program, day) if p.unit_retail and p.unit_retail > 0]
    for wanted in ([sku, "All"] if sku != "All" else ["All"]):
        hits = [p for p in active if p.sku == wanted]
        if hits:
            best = min(hits, key=lambda p: p.unit_retail)
            return Expected(best.unit_retail, f"Promo: {best.offer} ({best.start:%m/%d}-{best.end:%m/%d})")
    if program.base_price is not None:
        return Expected(program.base_price, "Base shelf price")
    return Expected(None, "Not set")


def price_check(expected: float | None, observed: float | None) -> str:
    if observed is None:
        return ""
    if expected is None:
        return "No plan price"
    if abs(observed - expected) < 0.005:
        return "Match"
    return "Over plan" if observed > expected else "Under plan"


def current_offer_text(program: Program, day: date) -> str:
    act = active_promos(program, day)
    if not act:
        return "None active"
    text = act[0].offer
    if len(act) > 1:
        text += f" (+{len(act) - 1} more)"
    return text


def next_promo_start(program: Program, day: date) -> date | None:
    future = [p.start for p in program.promos if p.start > day]
    return min(future) if future else None


def active_sku_prices(program: Program, day: date) -> list[tuple[str, float, str]]:
    """Lowest active retail per SKU: [(sku, price, offer)], for plan cards."""
    best: dict[str, Promo] = {}
    for p in active_promos(program, day):
        if p.unit_retail and p.unit_retail > 0 and (p.sku not in best or p.unit_retail < best[p.sku].unit_retail):
            best[p.sku] = p
    return [(k, v.unit_retail, v.offer) for k, v in sorted(best.items())]
