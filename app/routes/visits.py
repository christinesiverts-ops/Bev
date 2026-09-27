import math
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, pricing
from ..common import flash, opt_coord, opt_date, opt_float, opt_int, redirect, render, s, today, yn
from ..db import get_db
from ..models import DISPLAY_CHOICES, WIN_LOCATIONS, WIN_TYPES, AuditLine, Issue, IssueUpdate, Photo, Program, Store, User, Visit
from ..photos import save_upload, uploads_from
from ..security import csrf_protect, current_user, log, require_field
from ..seed import lists
from ..store_match import programs_for_store

router = APIRouter()


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def can_edit_visit(user: User, v: Visit) -> bool:
    return user.is_manager or (user.can_log_visits and v.rep_id == user.id)


def _visit_or_404(db, vid) -> Visit:
    v = db.get(Visit, vid)
    if not v:
        raise HTTPException(404)
    return v


def _editable(user, v):
    if not can_edit_visit(user, v):
        raise HTTPException(403, "You can only change your own visits.")


def _team(db):
    return db.scalars(select(User).where(User.active.is_(True), User.role != "viewer").order_by(User.display_name)).all()


# ---------------- check in ----------------
@router.get("/visits/new")
def visit_new(request: Request, store_id: int | None = None, q: str = "", user: User = Depends(require_field),
              db: Session = Depends(get_db)):
    st = db.get(Store, store_id) if store_id else None
    matches = []
    if not st and q:
        like = f"%{q}%"
        matches = db.scalars(select(Store).where(Store.active.is_(True), Store.store_number.ilike(like)
                                                 | Store.city.ilike(like) | Store.chain.ilike(like)
                                                 | Store.name.ilike(like)).order_by(Store.chain).limit(50)).all()
    return render(request, "visit_new.html", user=user, st=st, q=q, matches=matches)


@router.post("/visits/new", dependencies=[Depends(csrf_protect)])
async def visit_create(request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    form = await request.form()
    st = db.get(Store, opt_int(form.get("store_id")) or 0)
    if not st:
        raise HTTPException(400, "Pick a store first.")
    try:
        lat, lng, acc = opt_coord(form.get("lat")), opt_coord(form.get("lng")), opt_float(form.get("accuracy"))
    except ValueError:
        lat = lng = acc = None
    if lat is not None and not (-90 <= lat <= 90 and -180 <= (lng or 0) <= 180):
        lat = lng = None
    v = Visit(store_id=st.id, rep_id=user.id, visit_date=today(), checkin_lat=lat, checkin_lng=lng,
              checkin_accuracy_m=acc)
    if lat is not None and lng is not None and st.lat is not None and st.lng is not None:
        v.distance_m = round(haversine_m(lat, lng, st.lat, st.lng))
    elif (lat is not None and lng is not None and st.lat is None and acc is not None
          and acc <= config.LEARN_STORE_GPS_MAX_ACCURACY_M):
        st.lat, st.lng = lat, lng          # first accurate check-in teaches the map where the store is
        v.distance_m = 0
        log(db, user, "learn_location", "store", st.id, f"{st.label} from check-in (±{acc:.0f} m)")
    db.add(v)
    db.flush()
    log(db, user, "check_in", "visit", v.id, f"{st.label} gps={'yes' if lat is not None else 'no'} dist={v.distance_m}")
    db.commit()
    return redirect(f"/visits/{v.id}")


# ---------------- visit page ----------------
@router.get("/visits/{vid}")
def visit_detail(vid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    v = _visit_or_404(db, vid)
    matched, other = programs_for_store(db, v.store)
    day = v.visit_date
    cards = [{"p": p, "offer": pricing.current_offer_text(p, day), "expected": pricing.expected_price(p, "All", day),
              "sku_prices": pricing.active_sku_prices(p, day)}
             for p in matched]
    prev = db.scalars(select(Visit).where(Visit.store_id == v.store_id, Visit.id != v.id,
                                          Visit.checked_in_at < v.checked_in_at)
                      .order_by(Visit.checked_in_at.desc()).limit(3)).all()
    issues = db.scalars(select(Issue).where(Issue.store_id == v.store_id, Issue.status != "Resolved")
                        .order_by(Issue.created_at.desc())).all()
    L = lists()
    plan_json = {}
    for p in matched + other:
        plan_json[p.id] = {sku: _exp_dict(pricing.expected_price(p, sku, day)) for sku in L["skus"]}
    from .wins import placements_at_store
    checked = {}
    for l in v.lines:
        checked.setdefault(l.program_id, []).append(l)
    for c in cards:
        c["lines"] = checked.get(c["p"].id, [])
    return render(request, "visit_detail.html", user=user, v=v, cards=cards, other=other, prev=prev, issues=issues,
                  plan_json=plan_json, matched=matched, placements=placements_at_store(db, v.store_id, v.id),
                  win_types=WIN_TYPES, win_locations=WIN_LOCATIONS, brands=L["brands"],
                  other_lines=[l for l in v.lines if l.program_id not in {c["p"].id for c in cards}],
                  editable=can_edit_visit(user, v), skus=L["skus"], dtypes=L["discrepancy_types"],
                  display_choices=DISPLAY_CHOICES, team=_team(db), default_due=today() + timedelta(days=7),
                  gps_flag=config.GPS_FLAG_METERS)


def _exp_dict(e):
    return {"price": e.price, "basis": e.basis}


def _fill_line(line: AuditLine, form, program: Program, visit_day: date) -> None:
    line.program_id = program.id
    line.sku = s(form.get("sku")) or "All"
    try:
        line.observed_price = opt_float(form.get("observed_price"))
    except ValueError as e:
        raise HTTPException(400, f"Observed price: {e}")
    exp = pricing.expected_price(program, line.sku, visit_day)
    line.expected_price, line.expected_basis = exp.price, exp.basis
    line.price_check = pricing.price_check(exp.price, line.observed_price)
    line.tag_ok = yn(form.get("tag_ok"))
    line.planogram_ok = yn(form.get("planogram_ok"))
    line.in_stock_ok = yn(form.get("in_stock_ok"))
    disp = s(form.get("display"))
    line.display = disp if disp in DISPLAY_CHOICES else ""
    dtype = s(form.get("discrepancy_type")) or "None"
    if dtype == "None" and line.price_check in ("Over plan", "Under plan"):
        dtype = "Price - over plan" if line.price_check == "Over plan" else "Price - under plan"
    line.discrepancy_type = dtype
    line.notes = s(form.get("notes"))


def _maybe_issue(db, user, v: Visit, line: AuditLine, form) -> Issue | None:
    if line.discrepancy_type == "None":
        return None
    existing = db.scalar(select(Issue).where(Issue.audit_line_id == line.id))
    if existing:
        existing.discrepancy_type = line.discrepancy_type
        return existing
    try:
        due = opt_date(form.get("due_date")) or (today() + timedelta(days=7))
    except ValueError as e:
        raise HTTPException(400, f"Due date: {e}")
    owner_id = opt_int(form.get("owner_id")) or user.id
    if not db.get(User, owner_id):
        owner_id = user.id
    desc = line.notes or line.discrepancy_type
    if line.price_check in ("Over plan", "Under plan"):
        desc = (f"Shelf ${line.observed_price:.2f} vs plan ${line.expected_price:.2f} ({line.sku}). " + (line.notes or "")).strip()
    iss = Issue(store_id=v.store_id, program_id=line.program_id, audit_line_id=line.id,
                discrepancy_type=line.discrepancy_type, description=desc, action=s(form.get("action")),
                owner_id=owner_id, due_date=due, status="Open", created_by_id=user.id)
    db.add(iss)
    db.flush()
    db.add(IssueUpdate(issue_id=iss.id, user_id=user.id, status="Open", note="Raised during visit"))
    log(db, user, "create", "issue", iss.id, f"{v.store.label}: {iss.discrepancy_type}")
    return iss


@router.post("/visits/{vid}/lines", dependencies=[Depends(csrf_protect)])
async def line_add(vid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    v = _visit_or_404(db, vid)
    _editable(user, v)
    form = await request.form()
    program = db.get(Program, opt_int(form.get("program_id")) or 0)
    if not program or not program.active:
        raise HTTPException(400, "Pick the program you checked.")
    line = AuditLine(visit_id=v.id)
    _fill_line(line, form, program, v.visit_date)
    db.add(line)
    db.flush()
    for up in uploads_from(form, "photos"):
        name = await save_upload(up)
        if name:
            db.add(Photo(visit_id=v.id, audit_line_id=line.id, filename=name, uploaded_by_id=user.id))
    iss = _maybe_issue(db, user, v, line, form)
    log(db, user, "create", "audit_line", line.id, f"{program.code} {line.price_check} {line.discrepancy_type}")
    db.commit()
    msg = f"Saved {program.brand} check"
    if line.price_check:
        msg += f": {line.price_check}"
    if iss:
        msg += f". Follow-up #{iss.id} opened."
    flash(request, msg, "warn" if iss else "ok")
    return redirect(f"/visits/{v.id}#lines")


@router.get("/lines/{lid}/edit")
def line_edit(lid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    line = db.get(AuditLine, lid)
    if not line:
        raise HTTPException(404)
    _editable(user, line.visit)
    L = lists()
    return render(request, "line_form.html", user=user, line=line, skus=L["skus"], dtypes=L["discrepancy_types"],
                  display_choices=DISPLAY_CHOICES)


@router.post("/lines/{lid}/edit", dependencies=[Depends(csrf_protect)])
async def line_update(lid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    line = db.get(AuditLine, lid)
    if not line:
        raise HTTPException(404)
    v = line.visit
    _editable(user, v)
    form = await request.form()
    _fill_line(line, form, line.program, v.visit_date)
    for up in uploads_from(form, "photos"):
        name = await save_upload(up)
        if name:
            db.add(Photo(visit_id=v.id, audit_line_id=line.id, filename=name, uploaded_by_id=user.id))
    _maybe_issue(db, user, v, line, form)
    log(db, user, "update", "audit_line", line.id, f"{line.program.code} {line.price_check} {line.discrepancy_type}")
    db.commit()
    flash(request, "Check updated.")
    return redirect(f"/visits/{v.id}#lines")


@router.post("/lines/{lid}/delete", dependencies=[Depends(csrf_protect)])
def line_delete(lid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    line = db.get(AuditLine, lid)
    if not line:
        raise HTTPException(404)
    v = line.visit
    _editable(user, v)
    log(db, user, "delete", "audit_line", line.id, f"{line.program.code} visit {v.id}")
    db.delete(line)
    db.commit()
    flash(request, "Check removed.")
    return redirect(f"/visits/{v.id}#lines")


@router.post("/visits/{vid}/notes", dependencies=[Depends(csrf_protect)])
async def visit_notes(vid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    v = _visit_or_404(db, vid)
    _editable(user, v)
    form = await request.form()
    v.notes = s(form.get("notes"))
    for up in uploads_from(form, "photos"):
        name = await save_upload(up)
        if name:
            db.add(Photo(visit_id=v.id, filename=name, uploaded_by_id=user.id))
    log(db, user, "update", "visit", v.id, "notes/photos")
    db.commit()
    flash(request, "Visit notes saved.")
    return redirect(f"/visits/{v.id}#notes")


@router.post("/visits/{vid}/checkout", dependencies=[Depends(csrf_protect)])
def visit_checkout(vid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    v = _visit_or_404(db, vid)
    _editable(user, v)
    if v.checked_out_at is None:
        v.checked_out_at = datetime.utcnow()
        log(db, user, "check_out", "visit", v.id, v.store.label)
        db.commit()
    flash(request, f"Checked out of {v.store.label}. Here's your recap to share.")
    return redirect(f"/visits/{v.id}/recap")


@router.post("/visits/{vid}/delete", dependencies=[Depends(csrf_protect)])
def visit_delete(vid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    v = _visit_or_404(db, vid)
    _editable(user, v)
    if v.lines and not user.is_manager:
        raise HTTPException(400, "Remove the checks first, or ask your manager to delete this visit.")
    log(db, user, "delete", "visit", v.id, v.store.label)
    db.delete(v)
    db.commit()
    flash(request, "Visit deleted.")
    return redirect("/")


# ---------------- lists ----------------
@router.get("/visits")
def visit_list(request: Request, rep: int | None = None, chain: str = "", start: str = "", end: str = "",
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Visit).join(Store)
    if rep:
        stmt = stmt.where(Visit.rep_id == rep)
    if chain:
        stmt = stmt.where(Store.chain == chain)
    try:
        if start:
            stmt = stmt.where(Visit.visit_date >= opt_date(start))
        if end:
            stmt = stmt.where(Visit.visit_date <= opt_date(end))
    except ValueError as e:
        raise HTTPException(400, str(e))
    visits = db.scalars(stmt.order_by(Visit.checked_in_at.desc()).limit(300)).all()
    chains = db.scalars(select(Store.chain).distinct().order_by(Store.chain)).all()
    return render(request, "visits.html", user=user, visits=visits, team=_team(db), chains=chains,
                  f={"rep": rep, "chain": chain, "start": start, "end": end}, gps_flag=config.GPS_FLAG_METERS)


# ---------------- photos ----------------
@router.get("/photos/{pid}")
def photo(pid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ph = db.get(Photo, pid)
    if not ph:
        raise HTTPException(404)
    path = config.PHOTO_DIR / ph.filename
    if not path.is_file():
        raise HTTPException(404, "Photo file missing.")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/photos/{pid}/delete", dependencies=[Depends(csrf_protect)])
def photo_delete(pid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    ph = db.get(Photo, pid)
    if not ph:
        raise HTTPException(404)
    _editable(user, ph.visit)
    vid = ph.visit_id
    (config.PHOTO_DIR / ph.filename).unlink(missing_ok=True)
    log(db, user, "delete", "photo", ph.id, f"visit {vid}")
    db.delete(ph)
    db.commit()
    flash(request, "Photo deleted.")
    return redirect(f"/visits/{vid}")
