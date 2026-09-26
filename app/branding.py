"""Company branding: name, colors, logos. Brand + chain logos with uploaded overrides."""
import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from . import config
from .models import Setting

STATIC_LOGOS = Path(__file__).parent / "static" / "logos"
DEFAULTS = {"company_name": "Chain Audit", "primary_color": "#6E1E2E", "accent_color": "#B7791F", "company_logo": ""}

BRAND_SLUGS = {"ZOA": "zoa", "Henry's": "henrys", "Fever-Tree": "fever-tree", "Naked Life": "naked-life"}
BRAND_COLORS = {"ZOA": "#0F6B78", "Henry's": "#7A1F2B", "Fever-Tree": "#8A5A19", "Naked Life": "#2F7D32"}
CHAIN_SLUGS = {
    "Albertsons/Safeway": "albertsons", "Save Mart / Lucky": "save-mart", "Raley's": "raleys", "Bi-Mart": "bi-mart",
    "Bashas'": "bashas", "BevMo!": "bevmo", "C&K Market": "ck-market", "Kroger": "kroger",
    "Nugget Markets": "nugget-markets", "Stater Bros.": "stater-bros", "Plaid Pantry": "plaid-pantry",
    "WinCo Foods": "winco-foods", "Metropolitan Market": "metropolitan-market",
    "Northwest Grocers (NWG)": "northwest-grocers", "Town & Country Markets": "town-country-markets",
    "Harvest Foods": "harvest-foods", "Ridley's Family Markets": "ridleys", "Rosauers": "rosauers",
    "Yoke's Fresh Market": "yokes", "Harmons": "harmons", "Whole Foods Market": "whole-foods-market",
    "Smart & Final": "smart-final",
}
KINDS = {"brands": "png", "products": "jpg", "chains": "png", "company": "png"}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("&", "").replace("'", "")).strip("-")


def brand_slug(brand: str) -> str:
    return BRAND_SLUGS.get(brand, slugify(brand))


def chain_slug(chain: str) -> str:
    return CHAIN_SLUGS.get(chain, slugify(chain))


def upload_dir(kind: str) -> Path:
    return config.DATA_DIR / "branding" / kind


def logo_url(kind: str, slug: str) -> str | None:
    """Uploaded override first, then the bundled asset, else None."""
    ext = KINDS[kind]
    up = upload_dir(kind) / f"{slug}.{ext}"
    if up.is_file():
        return f"/branding/{kind}/{slug}.{ext}?v={int(up.stat().st_mtime)}"
    if (STATIC_LOGOS / kind / f"{slug}.{ext}").is_file():
        return f"/static/logos/{kind}/{slug}.{ext}"
    return None


# ---------------- settings ----------------
def get_settings(db: Session) -> dict:
    vals = dict(DEFAULTS)
    for row in db.query(Setting).all():
        vals[row.key] = row.value
    return vals


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


# ---------------- color math (WCAG) ----------------
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lum(rgb) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = _lum(_rgb(a)), _lum(_rgb(b))
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ra, rb))


def triplet(h: str) -> str:
    return " ".join(str(c) for c in _rgb(h))


def validate_brand_colors(primary: str, accent: str) -> str | None:
    if not HEX_RE.match(primary) or not HEX_RE.match(accent):
        return "Colors must be hex values like #6E1E2E."
    if contrast(primary, "#FFFFFF") < 4.5:
        return (f"The primary color is too light for white button text (contrast {contrast(primary, '#FFFFFF'):.1f}:1, "
                "needs 4.5:1). Pick a darker shade.")
    return None


def _readable_on(fg: str, bg: str, toward: str, target: float = 4.5) -> str:
    """Nudge fg toward `toward` until it reads on bg."""
    c, t = fg, 0.0
    while contrast(c, bg) < target and t < 1:
        t += 0.05
        c = mix(fg, toward, t)
    return c


@lru_cache(maxsize=32)
def theme_css(primary: str, accent: str) -> str:
    light_accent_text = _readable_on(accent, "#FFFFFF", "#000000")
    dark_primary = primary if contrast(primary, "#FFFFFF") >= 4.5 else mix(primary, "#000000", .3)
    dark_primary_text = _readable_on(mix(primary, "#FFFFFF", .35), "#1C1A18", "#FFFFFF")
    dark_accent = _readable_on(accent, "#1C1A18", "#FFFFFF")
    return (
        f":root{{--primary:{triplet(primary)};--primary-text:{triplet(primary)};--accent:{triplet(accent)};"
        f"--accent-text:{triplet(light_accent_text)}}}\n"
        f":root[data-theme=dark]{{--primary:{triplet(dark_primary)};--primary-text:{triplet(dark_primary_text)};"
        f"--accent:{triplet(dark_accent)};--accent-text:{triplet(dark_accent)}}}\n"
    )


# ---------------- cached site settings for templates ----------------
_cache: dict = {"v": None}


def site() -> dict:
    if _cache["v"] is None:
        from .db import SessionLocal
        with SessionLocal() as s:
            _cache["v"] = get_settings(s)
    return _cache["v"]


def invalidate() -> None:
    _cache["v"] = None
