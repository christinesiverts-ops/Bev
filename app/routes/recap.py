from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import recap
from ..common import opt_date, render, today
from ..db import get_db
from ..models import User, Visit
from ..security import current_user, log

router = APIRouter()


def _visit(db, vid) -> Visit:
    v = db.get(Visit, vid)
    if not v:
        raise HTTPException(404)
    return v


def _pdf(body: bytes, name: str) -> Response:
    return Response(body, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"', "Cache-Control": "private, no-store"})


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s).strip("-").lower()


@router.get("/visits/{vid}/recap")
def visit_recap(vid: int, request: Request, audience: str = "team", user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    v = _visit(db, vid)
    audience = "store" if audience == "store" else "team"
    return render(request, "recap_visit.html", user=user, r=recap.build_visit(db, v), audience=audience)


@router.get("/visits/{vid}/recap.pdf")
def visit_recap_pdf(vid: int, audience: str = "team", photos: int = 1, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    v = _visit(db, vid)
    audience = "store" if audience == "store" else "team"
    body = recap.visit_pdf(recap.build_visit(db, v), audience=audience, include_photos=bool(photos))
    log(db, user, "export", "recap", v.id, f"visit pdf ({audience})")
    db.commit()
    return _pdf(body, f"recap-{_slug(v.store.chain)}-{v.store.store_number}-{v.visit_date:%Y%m%d}.pdf")


def _day_args(db, user, rep, day):
    rep_user = db.get(User, rep) if rep else user
    if not rep_user:
        raise HTTPException(404)
    try:
        d = opt_date(day) or today()
    except ValueError as e:
        raise HTTPException(400, str(e))
    return rep_user, d


@router.get("/recap/day")
def day_recap(request: Request, rep: int | None = None, day: str = "", user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    rep_user, d = _day_args(db, user, rep, day)
    team = db.scalars(select(User).where(User.active.is_(True), User.role != "viewer").order_by(User.display_name)).all()
    return render(request, "recap_day.html", user=user, d=recap.build_day(db, rep_user, d), team=team)


@router.get("/recap/day.pdf")
def day_recap_pdf(rep: int | None = None, day: str = "", user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    rep_user, d = _day_args(db, user, rep, day)
    body = recap.day_pdf(recap.build_day(db, rep_user, d))
    return _pdf(body, f"day-recap-{_slug(rep_user.display_name)}-{d:%Y%m%d}.pdf")
