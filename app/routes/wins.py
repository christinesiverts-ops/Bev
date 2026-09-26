from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..common import flash, opt_int, redirect, render, s, today
from ..db import get_db
from ..models import TRACKED_WIN_TYPES, WIN_LOCATIONS, WIN_TYPES, Photo, Program, Store, User, Visit, Win, WinCheck
from ..photos import save_upload, uploads_from
from ..security import csrf_protect, current_user, log, require_field
from ..seed import lists

router = APIRouter()


def _back(form, default: str) -> str:
    b = s(form.get("back"))
    return b if b.startswith("/") and not b.startswith("//") else default


@router.post("/visits/{vid}/wins", dependencies=[Depends(csrf_protect)])
async def win_create(vid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    v = db.get(Visit, vid)
    if not v:
        raise HTTPException(404)
    if not (user.is_manager or v.rep_id == user.id):
        raise HTTPException(403, "You can only add wins to your own visits.")
    form = await request.form()
    win_type = s(form.get("win_type"))
    if win_type not in {t for t, _ in WIN_TYPES}:
        raise HTTPException(400, "Pick what kind of win this is.")
    program = db.get(Program, opt_int(form.get("program_id")) or 0)
    brand = program.brand if program else s(form.get("brand"))
    if not brand:
        raise HTTPException(400, "Pick the brand or program.")
    location = s(form.get("location"))
    try:
        cases, facings = opt_int(form.get("cases")), opt_int(form.get("facings"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    w = Win(visit_id=v.id, store_id=v.store_id, program_id=program.id if program else None, brand=brand,
            win_type=win_type, location=location if location in WIN_LOCATIONS else "", cases=cases, facings=facings,
            notes=s(form.get("notes")), tracked=win_type in TRACKED_WIN_TYPES, status="Active",
            last_checked=v.visit_date, created_by_id=user.id)
    db.add(w)
    db.flush()
    for up in uploads_from(form, "photos"):
        name = await save_upload(up)
        if name:
            db.add(Photo(visit_id=v.id, win_id=w.id, filename=name, uploaded_by_id=user.id))
    log(db, user, "create", "win", w.id, f"{v.store.label}: {brand} {win_type}")
    db.commit()
    flash(request, f"Win logged: {win_type} · {brand}. Nice work.", "win")
    return redirect(f"/visits/{v.id}#wins")


@router.post("/wins/{wid}/check", dependencies=[Depends(csrf_protect)])
async def win_check(wid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    w = db.get(Win, wid)
    if not w:
        raise HTTPException(404)
    form = await request.form()
    status = s(form.get("status"))
    if status not in ("Active", "Gone"):
        raise HTTPException(400, "Mark it as still up or gone.")
    visit_id = opt_int(form.get("visit_id"))
    w.status = status
    w.last_checked = today()
    db.add(WinCheck(win_id=w.id, visit_id=visit_id, user_id=user.id, status=status, note=s(form.get("note"))))
    log(db, user, "check", "win", w.id, f"{w.win_type} -> {status}")
    db.commit()
    flash(request, "Placement confirmed. Still up." if status == "Active" else "Marked as gone. Consider logging a follow-up.",
          "ok" if status == "Active" else "warn")
    return redirect(_back(form, f"/stores/{w.store_id}"))


@router.post("/wins/{wid}/delete", dependencies=[Depends(csrf_protect)])
async def win_delete(wid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    w = db.get(Win, wid)
    if not w:
        raise HTTPException(404)
    if not (user.is_manager or w.created_by_id == user.id):
        raise HTTPException(403, "You can only remove your own wins.")
    form = await request.form()
    for ph in w.photos:
        (config.PHOTO_DIR / ph.filename).unlink(missing_ok=True)
        db.delete(ph)
    log(db, user, "delete", "win", w.id, f"{w.win_type} {w.brand}")
    db.delete(w)
    db.commit()
    flash(request, "Win removed.")
    return redirect(_back(form, "/wins"))


@router.get("/wins")
def win_list(request: Request, brand: str = "", win_type: str = "", rep: int | None = None, status: str = "",
             days: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)):
    days = days if days in (7, 30, 90, 365) else 30
    since = today() - timedelta(days=days)
    stmt = select(Win).join(Visit).where(Visit.visit_date >= since)
    if brand:
        stmt = stmt.where(Win.brand == brand)
    if win_type:
        stmt = stmt.where(Win.win_type == win_type)
    if rep:
        stmt = stmt.where(Win.created_by_id == rep)
    if status in ("Active", "Gone"):
        stmt = stmt.where(Win.tracked.is_(True), Win.status == status)
    wins = db.scalars(stmt.order_by(Win.created_at.desc()).limit(400)).all()
    team = db.scalars(select(User).where(User.active.is_(True), User.role != "viewer").order_by(User.display_name)).all()
    return render(request, "wins.html", user=user, wins=wins, team=team, brands=lists()["brands"],
                  win_types=[t for t, _ in WIN_TYPES], days=days,
                  f={"brand": brand, "win_type": win_type, "rep": rep, "status": status})


def placements_at_store(db: Session, store_id: int, exclude_visit: int | None = None) -> list[Win]:
    stmt = select(Win).where(Win.store_id == store_id, Win.tracked.is_(True), Win.status == "Active")
    if exclude_visit:
        stmt = stmt.where(Win.visit_id != exclude_visit)
    return db.scalars(stmt.order_by(Win.created_at.desc())).all()
