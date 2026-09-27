"""Why a store needs a visit: overdue/open follow-ups, placements due a re-check, time since last visit."""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Issue, Store, Visit, Win

STALE_DAYS = 30
PLACEMENT_RECHECK_DAYS = 14


def store_flags(db: Session, today: date) -> dict[int, dict]:
    last = dict(db.execute(select(Visit.store_id, func.max(Visit.visit_date)).group_by(Visit.store_id)).all())
    open_issues: dict[int, list[Issue]] = {}
    for i in db.scalars(select(Issue).where(Issue.status != "Resolved")).all():
        open_issues.setdefault(i.store_id, []).append(i)
    placements: dict[int, int] = {}
    for w in db.scalars(select(Win).where(Win.tracked.is_(True), Win.status == "Active")).all():
        if not w.last_checked or (today - w.last_checked).days >= PLACEMENT_RECHECK_DAYS:
            placements[w.store_id] = placements.get(w.store_id, 0) + 1
    out = {}
    for sid in {s for (s,) in db.execute(select(Store.id).where(Store.active.is_(True))).all()}:
        iss = open_issues.get(sid, [])
        overdue = sum(1 for i in iss if i.due_date and i.due_date < today)
        lv = last.get(sid)
        days = (today - lv).days if lv else None
        reasons = []
        if overdue:
            reasons.append(f"{overdue} overdue follow-up{'s' if overdue > 1 else ''}")
        elif iss:
            reasons.append(f"{len(iss)} open follow-up{'s' if len(iss) > 1 else ''}")
        if placements.get(sid):
            reasons.append(f"{placements[sid]} placement{'s' if placements[sid] > 1 else ''} to re-check")
        if lv is None:
            reasons.append("never visited")
        elif days >= STALE_DAYS:
            reasons.append(f"not visited in {days} days")
        level = "urgent" if overdue else "due" if (iss or placements.get(sid) or lv is None or days >= STALE_DAYS) else "ok"
        out[sid] = {"last": lv, "days": days, "open": len(iss), "overdue": overdue,
                    "placements": placements.get(sid, 0), "reasons": reasons, "level": level}
    return out
