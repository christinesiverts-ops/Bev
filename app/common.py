"""Shared web helpers: templates, flash messages, form parsing, local 'today'."""
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import config
from .security import csrf_token

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def today() -> date:
    return datetime.now(config.TIMEZONE).date()


def local_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.replace(tzinfo=timezone.utc).astimezone(config.TIMEZONE).strftime("%m/%d/%Y %I:%M %p")


def money(v) -> str:
    return "" if v is None else f"${v:,.2f}"


def fmt_date(d) -> str:
    return d.strftime("%m/%d/%Y") if d else ""


templates.env.filters["money"] = money
templates.env.filters["d"] = fmt_date
templates.env.filters["local"] = local_dt
templates.env.globals["today"] = today


def flash(request: Request, message: str, kind: str = "ok") -> None:
    request.session.setdefault("flash", []).append([kind, message])


def render(request: Request, name: str, user=None, status_code: int = 200, **ctx):
    msgs = request.session.pop("flash", [])
    return templates.TemplateResponse(
        request, name, {"user": user, "csrf": csrf_token(request), "flashes": msgs, **ctx}, status_code=status_code)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


# ---- form value parsing ----
def s(v) -> str:
    return (v or "").strip() if isinstance(v, str) or v is None else str(v).strip()


def opt_float(v) -> float | None:
    v = s(v).replace("$", "").replace(",", "")
    if not v:
        return None
    try:
        return round(float(v), 2)
    except ValueError:
        raise ValueError(f"'{v}' is not a number")


def opt_int(v) -> int | None:
    v = s(v)
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        raise ValueError(f"'{v}' is not a whole number")


def opt_date(v) -> date | None:
    v = s(v)
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"'{v}' is not a date")


def yn(v) -> bool | None:
    v = s(v).upper()
    return True if v in ("Y", "YES", "TRUE", "1") else False if v in ("N", "NO", "FALSE", "0") else None
