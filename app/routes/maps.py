from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import branding, config, geocode, routing
from ..attention import store_flags
from ..common import flash, opt_coord, opt_date, opt_int, redirect, render, s, today
from ..db import get_db
from ..models import Route, RouteStop, Store, User, Visit
from ..security import csrf_protect, current_user, log, require_field, require_manager

router = APIRouter()


def _team(db):
    return db.scalars(select(User).where(User.active.is_(True), User.role != "viewer").order_by(User.display_name)).all()


def _can_edit(user: User, r: Route) -> bool:
    return user.is_manager or (user.can_log_visits and r.assignee_id == user.id)


def _route_or_404(db, rid) -> Route:
    r = db.get(Route, rid)
    if not r:
        raise HTTPException(404)
    return r


def _pt(st: Store):
    return (st.lat, st.lng) if st.lat is not None and st.lng is not None else None


@router.get("/map")
def map_page(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stores = db.scalars(select(Store).where(Store.active.is_(True))).all()
    missing = [s_ for s_ in stores if s_.lat is None]
    chains = sorted({s_.chain for s_ in stores})
    return render(request, "map.html", user=user, chains=chains, team=_team(db), t=today(),
                  n_stores=len(stores), n_missing=len(missing),
                  n_geocodable=sum(1 for s_ in missing if geocode.store_query(s_)), geo=geocode.state,
                  tiles={"url": config.MAP_TILE_URL, "attribution": config.MAP_TILE_ATTRIBUTION})


@router.get("/map/stores.json")
def map_stores(user: User = Depends(current_user), db: Session = Depends(get_db)):
    flags = store_flags(db, today())
    out = []
    for st in db.scalars(select(Store).where(Store.active.is_(True)).order_by(Store.chain, Store.store_number)).all():
        f = flags.get(st.id, {})
        out.append({"id": st.id, "label": st.label, "chain": st.chain, "number": st.store_number,
                    "address": " ".join(x for x in (st.address, st.city, st.state) if x),
                    "lat": st.lat, "lng": st.lng, "level": f.get("level", "ok"), "reasons": f.get("reasons", []),
                    "last": f["last"].strftime("%m/%d/%Y") if f.get("last") else None, "open": f.get("open", 0),
                    "logo": branding.logo_url("chains", branding.chain_slug(st.chain))})
    return JSONResponse(out, headers={"Cache-Control": "no-store"})


@router.post("/map/geocode", dependencies=[Depends(csrf_protect)])
def map_geocode(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    n = geocode.start(db)
    log(db, user, "geocode", "store", None, f"queued={n}")
    db.commit()
    if geocode.state.get("error") and not n:
        flash(request, geocode.state["error"], "warn")
    else:
        flash(request, f"Looking up {n} store addresses in the background (about {max(1, round(n * 1.1 / 60))} min). "
                       "Refresh the map to see them appear." if n else "No stores with an address are missing a location.")
    return redirect("/map")


# ---------------- routes ----------------
def _order_stops(stores: list[Store], start) -> list[Store]:
    located = [s_ for s_ in stores if _pt(s_)]
    unlocated = [s_ for s_ in stores if not _pt(s_)]
    order = routing.optimize([_pt(s_) for s_ in located], start)
    return [located[i] for i in order] + unlocated


@router.post("/routes", dependencies=[Depends(csrf_protect)])
async def route_create(request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(x) for x in form.getlist("store_id") if s(x).isdigit()]
    stores = [st for st in (db.get(Store, i) for i in dict.fromkeys(ids)) if st and st.active]
    if not stores:
        raise HTTPException(400, "Pick at least one store for the route.")
    if len(stores) > 40:
        raise HTTPException(400, "Keep a route to 40 stops or fewer.")
    try:
        route_date = opt_date(form.get("route_date")) or today()
        start_lat, start_lng = opt_coord(form.get("start_lat")), opt_coord(form.get("start_lng"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    assignee_id = user.id
    if user.is_manager and opt_int(form.get("assignee_id")):
        a = db.get(User, opt_int(form.get("assignee_id")))
        if not a or not a.active or a.role == "viewer":
            raise HTTPException(400, "Pick an active rep.")
        assignee_id = a.id
    start = (start_lat, start_lng) if start_lat is not None and start_lng is not None else None
    ordered = _order_stops(stores, start) if form.get("optimize", "Y") == "Y" else stores
    flags = store_flags(db, today())
    assignee = db.get(User, assignee_id)
    name = s(form.get("name")) or f"{assignee.display_name.split(' ')[0]}'s route · {route_date:%a %b} {route_date.day}"
    r = Route(name=name[:120], route_date=route_date, assignee_id=assignee_id, created_by_id=user.id,
              start_lat=start_lat, start_lng=start_lng, notes=s(form.get("notes")))
    db.add(r)
    db.flush()
    for pos, st in enumerate(ordered):
        db.add(RouteStop(route_id=r.id, store_id=st.id, position=pos,
                         reason="; ".join(flags.get(st.id, {}).get("reasons", []))[:200]))
    log(db, user, "create", "route", r.id, f"{name}: {len(ordered)} stops for user {assignee_id}")
    db.commit()
    flash(request, f"Route planned: {len(ordered)} stops" + (f" for {assignee.display_name}." if assignee_id != user.id else "."))
    return redirect(f"/routes/{r.id}")


def route_view(db: Session, r: Route) -> dict:
    visited = {v.store_id: v for v in db.scalars(select(Visit).where(Visit.rep_id == r.assignee_id,
                                                                      Visit.visit_date == r.route_date)).all()}
    start = (r.start_lat, r.start_lng) if r.start_lat is not None else None
    pts = [_pt(stp.store) for stp in r.stops]
    located = [p for p in pts if p]
    leg_list = routing.legs(located, start)
    leg_iter = iter(leg_list)
    rows = []
    for stp, p in zip(r.stops, pts):
        rows.append({"stop": stp, "leg": next(leg_iter) if p else None, "visit": visited.get(stp.store_id)})
    done = sum(1 for x in rows if x["visit"])
    nxt = next((x for x in rows if not x["visit"]), None)
    remaining = [p for x, p in zip(rows, pts) if p and not x["visit"]]
    return {"rows": rows, "done": done, "next": nxt, "summary": routing.summary(leg_list, len(rows)),
            "links": routing.google_maps_links(located, start), "remaining_links": routing.google_maps_links(remaining),
            "unlocated": sum(1 for p in pts if not p)}


@router.get("/routes")
def route_list(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Route)
    if not user.is_manager and user.role != "viewer":
        stmt = stmt.where(Route.assignee_id == user.id)
    routes = db.scalars(stmt.order_by(Route.route_date.desc(), Route.id.desc()).limit(100)).all()
    t = today()
    views = {r.id: route_view(db, r) for r in routes[:30]}
    return render(request, "routes.html", user=user, routes=routes, views=views, t=t)


@router.get("/routes/{rid}")
def route_detail(rid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _route_or_404(db, rid)
    if not (user.is_manager or user.role == "viewer" or r.assignee_id == user.id):
        raise HTTPException(403, "This route belongs to someone else.")
    v = route_view(db, r)
    stops_json = [{"n": i + 1, "id": x["stop"].store.id, "label": x["stop"].store.label, "lat": x["stop"].store.lat,
                   "lng": x["stop"].store.lng, "done": bool(x["visit"])} for i, x in enumerate(v["rows"])]
    stores = db.scalars(select(Store).where(Store.active.is_(True)).order_by(Store.chain, Store.store_number)).all()
    on_route = {x["stop"].store_id for x in v["rows"]}
    return render(request, "route_detail.html", user=user, r=r, v=v, stops_json=stops_json, editable=_can_edit(user, r),
                  add_options=[st for st in stores if st.id not in on_route], t=today(),
                  tiles={"url": config.MAP_TILE_URL, "attribution": config.MAP_TILE_ATTRIBUTION},
                  start=[r.start_lat, r.start_lng] if r.start_lat is not None else None)


@router.post("/routes/{rid}/optimize", dependencies=[Depends(csrf_protect)])
async def route_optimize(rid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    r = _route_or_404(db, rid)
    if not _can_edit(user, r):
        raise HTTPException(403, "You can only change your own routes.")
    form = await request.form()
    try:
        lat, lng = opt_coord(form.get("lat")), opt_coord(form.get("lng"))
    except ValueError:
        lat = lng = None
    visited = {v.store_id for v in db.scalars(select(Visit).where(Visit.rep_id == r.assignee_id,
                                                                  Visit.visit_date == r.route_date)).all()}
    done = [stp for stp in r.stops if stp.store_id in visited]
    todo = [stp for stp in r.stops if stp.store_id not in visited]
    start = (lat, lng) if lat is not None and lng is not None else None
    if start and not done:
        r.start_lat, r.start_lng = lat, lng
    order = _order_stops([stp.store for stp in todo], start)
    by_store = {stp.store_id: stp for stp in todo}
    for pos, stp in enumerate(done + [by_store[st.id] for st in order]):
        stp.position = pos
    log(db, user, "optimize", "route", r.id, f"from={'gps' if start else 'none'}")
    db.commit()
    flash(request, "Remaining stops re-ordered" + (" from where you are." if start else "."))
    return redirect(f"/routes/{r.id}")


@router.post("/routes/{rid}/stops", dependencies=[Depends(csrf_protect)])
async def route_add_stop(rid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    r = _route_or_404(db, rid)
    if not _can_edit(user, r):
        raise HTTPException(403, "You can only change your own routes.")
    form = await request.form()
    st = db.get(Store, opt_int(form.get("store_id")) or 0)
    if not st:
        raise HTTPException(400, "Pick a store.")
    if any(stp.store_id == st.id for stp in r.stops):
        raise HTTPException(400, "That store is already on the route.")
    db.add(RouteStop(route_id=r.id, store_id=st.id, position=len(r.stops)))
    log(db, user, "add_stop", "route", r.id, st.label)
    db.commit()
    flash(request, f"Added {st.label}. Tap Re-optimize to fit it in.")
    return redirect(f"/routes/{r.id}")


@router.post("/routes/{rid}/stops/{sid}", dependencies=[Depends(csrf_protect)])
async def route_stop_action(rid: int, sid: int, request: Request, user: User = Depends(require_field),
                            db: Session = Depends(get_db)):
    r = _route_or_404(db, rid)
    if not _can_edit(user, r):
        raise HTTPException(403, "You can only change your own routes.")
    form = await request.form()
    stops = list(r.stops)
    idx = next((i for i, stp in enumerate(stops) if stp.id == sid), None)
    if idx is None:
        raise HTTPException(404)
    action = s(form.get("action"))
    if action == "remove":
        db.delete(stops.pop(idx))
    elif action in ("up", "down"):
        j = idx - 1 if action == "up" else idx + 1
        if 0 <= j < len(stops):
            stops[idx], stops[j] = stops[j], stops[idx]
    else:
        raise HTTPException(400, "Unknown action.")
    for pos, stp in enumerate(stops):
        stp.position = pos
    db.commit()
    return redirect(f"/routes/{r.id}#stops")


@router.post("/routes/{rid}/delete", dependencies=[Depends(csrf_protect)])
def route_delete(rid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    r = _route_or_404(db, rid)
    if not _can_edit(user, r):
        raise HTTPException(403, "You can only change your own routes.")
    log(db, user, "delete", "route", r.id, r.name)
    db.delete(r)
    db.commit()
    flash(request, "Route deleted.")
    return redirect("/routes")


def todays_route(db: Session, user: User, day: date) -> tuple[Route | None, dict | None]:
    r = db.scalar(select(Route).where(Route.assignee_id == user.id, Route.route_date == day).order_by(Route.id.desc()))
    return (r, route_view(db, r)) if r else (None, None)
