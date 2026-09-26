from collections import Counter, defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import pricing
from ..common import render, today
from ..db import get_db
from ..models import AuditLine, DataReviewItem, Issue, Program, Store, Task, User, Visit, Win
from ..security import current_user
from ..seed import lists

router = APIRouter()


@router.get("/dashboard")
def dashboard(request: Request, days: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)):
    days = days if days in (7, 30, 90) else 30
    t = today()
    since = t - timedelta(days=days)
    programs = db.scalars(select(Program).options(selectinload(Program.promos)).where(Program.active.is_(True))).all()
    active_promos = sum(len(pricing.active_promos(p, t)) for p in programs)
    starting_soon = sum(1 for p in programs for pr in p.promos if t < pr.start <= t + timedelta(days=14))
    visits = db.scalars(select(Visit).where(Visit.visit_date >= since)).all()
    wins = db.scalars(select(Win).join(Visit).where(Visit.visit_date >= since)).all()
    live_placements = db.scalars(select(Win).where(Win.tracked.is_(True), Win.status == "Active")).all()
    wins_by_rep = Counter(w.created_by_id for w in wins)
    wins_by_type = Counter(w.win_type for w in wins).most_common()
    lines = db.scalars(select(AuditLine).join(Visit).where(Visit.visit_date >= since)).all()
    open_issues = db.scalars(select(Issue).where(Issue.status != "Resolved")).all()
    overdue = [i for i in open_issues if i.due_date and i.due_date < t]
    checks = Counter(l.price_check for l in lines if l.price_check in ("Match", "Over plan", "Under plan"))
    n_checks = sum(checks.values())
    match_rate = (checks["Match"] / n_checks) if n_checks else None

    team = db.scalars(select(User).where(User.active.is_(True), User.role != "viewer").order_by(User.display_name)).all()
    by_rep = []
    last_visit = dict(db.execute(select(Visit.rep_id, func.max(Visit.visit_date)).group_by(Visit.rep_id)).all())
    open_tasks = Counter(t_.assignee_id for t_ in db.scalars(select(Task).where(Task.status == "Open")).all())
    v_by_rep = Counter(v.rep_id for v in visits)
    lines_by_rep = defaultdict(list)
    for l in lines:
        lines_by_rep[l.visit.rep_id].append(l)
    for u in team:
        rl = lines_by_rep[u.id]
        if u.is_manager and not (v_by_rep[u.id] or any(i.owner_id == u.id for i in open_issues) or open_tasks[u.id]):
            continue  # managers show up only when they're doing field work
        pc = [l for l in rl if l.price_check in ("Match", "Over plan", "Under plan")]
        by_rep.append({"u": u, "visits": v_by_rep[u.id], "checks": len(rl), "wins": wins_by_rep[u.id],
                       "match": (sum(1 for l in pc if l.price_check == "Match") / len(pc)) if pc else None,
                       "open": sum(1 for i in open_issues if i.owner_id == u.id),
                       "overdue": sum(1 for i in overdue if i.owner_id == u.id),
                       "tasks": open_tasks[u.id], "last": last_visit.get(u.id)})

    brand_rows = []
    for b in lists()["brands"]:
        bp = [p for p in programs if p.brand == b]
        bl = [l for l in lines if l.program.brand == b and l.price_check in ("Match", "Over plan", "Under plan")]
        brand_rows.append({"brand": b, "programs": len(bp), "wins": sum(1 for w in wins if w.brand == b),
                           "live": sum(1 for w in live_placements if w.brand == b),
                           "active": sum(len(pricing.active_promos(p, t)) for p in bp),
                           "confirm": sum(1 for p in bp if p.data_status != "Current (2026)"),
                           "open": sum(1 for i in open_issues if i.program and i.program.brand == b),
                           "match": (sum(1 for l in bl if l.price_check == "Match") / len(bl)) if bl else None})
    by_type = Counter(i.discrepancy_type for i in open_issues).most_common()

    stores = db.scalars(select(Store).where(Store.active.is_(True))).all()
    store_last = dict(db.execute(select(Visit.store_id, func.max(Visit.visit_date)).group_by(Visit.store_id)).all())
    stale = sorted([(st, store_last.get(st.id)) for st in stores
                    if not store_last.get(st.id) or store_last[st.id] < since],
                   key=lambda x: (x[1] is not None, x[1] or t))
    kpis = {
        "programs": len(programs),
        "confirm": sum(1 for p in programs if p.data_status != "Current (2026)"),
        "active_promos": active_promos, "starting_soon": starting_soon,
        "visits": len(visits), "checks": len(lines), "wins": len(wins), "live_placements": len(live_placements),
        "cases": sum(w.cases or 0 for w in wins), "open": len(open_issues), "overdue": len(overdue),
        "match_rate": match_rate, "n_checks": n_checks,
        "stores": len(stores), "stale": len(stale),
        "unverified": sum(1 for st in stores if not st.verified),
        "data_review_open": db.scalar(select(func.count(DataReviewItem.id)).where(DataReviewItem.resolved.is_(False))),
    }
    return render(request, "dashboard.html", user=user, k=kpis, by_rep=by_rep, brand_rows=brand_rows, by_type=by_type,
                  stale=stale[:25], days=days, t=t, checks=checks, wins_by_type=wins_by_type)
