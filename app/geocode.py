"""Optional address -> lat/lng lookup for stores (OpenStreetMap Nominatim, 1 request/second).

Runs in a background thread when a manager asks for it. Stores also learn their location from a
rep's first accurate GPS check-in, so this is only a head start.
"""
import json
import logging
import threading
import time
import urllib.parse
import urllib.request

from sqlalchemy import select

from . import config
from .db import SessionLocal
from .models import Store

log = logging.getLogger("audit.geocode")
_lock = threading.Lock()
state = {"running": False, "done": 0, "found": 0, "total": 0, "error": ""}


def lookup(query: str) -> tuple[float, float] | None:
    ua = "ChainAudit/1.0" + (f" ({config.GEOCODER_EMAIL})" if config.GEOCODER_EMAIL else "")
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "us"})
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return (float(data[0]["lat"]), float(data[0]["lon"])) if data else None


def store_query(st: Store) -> str | None:
    if not (st.address and (st.city or st.zip)):
        return None
    return ", ".join(x for x in (st.address, st.city, st.state, st.zip) if x)


def _run(store_ids: list[int]) -> None:
    try:
        for sid in store_ids:
            with SessionLocal() as db:
                st = db.get(Store, sid)
                q = store_query(st) if st else None
                if q and st.lat is None:
                    try:
                        hit = lookup(q)
                    except Exception as e:  # network / rate limit: stop early, keep what we have
                        state["error"] = f"Lookup stopped: {e}"
                        log.warning("Geocoding stopped: %s", e)
                        return
                    if hit:
                        st.lat, st.lng = hit
                        db.commit()
                        state["found"] += 1
            state["done"] += 1
            time.sleep(1.1)   # Nominatim usage policy: max 1 request per second
    finally:
        state["running"] = False


def start(db) -> int:
    """Queue every store that has an address but no coordinates. Returns how many were queued."""
    if config.GEOCODER != "nominatim":
        state["error"] = "Address lookup is turned off (GEOCODER=off)."
        return 0
    with _lock:
        if state["running"]:
            return 0
        ids = [s.id for s in db.scalars(select(Store).where(Store.active.is_(True), Store.lat.is_(None))).all()
               if store_query(s)]
        state.update(running=bool(ids), done=0, found=0, total=len(ids), error="")
    if ids:
        threading.Thread(target=_run, args=(ids,), name="geocode", daemon=True).start()
    return len(ids)
