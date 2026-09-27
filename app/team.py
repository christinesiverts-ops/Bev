"""What each team member is working on: live status, today's route, recent activity."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .models import AuditLog, AuditLine, Issue, Task, User, Visit, Win

ACTIVITY = {
    ("check_in", "visit"): "Checked in", ("check_out", "visit"): "Checked out",
    ("create", "audit_line"): "Logged a check", ("update", "audit_line"): "Edited a check",
    ("create", "win"): "Logged a win", ("check", "win"): "Re-checked a placement",
    ("create", "issue"): "Raised a follow-up", ("update", "issue"): "Updated a follow-up",
    ("complete", "task"): "Completed a task", ("create", "route"): "Planned a route",
    ("optimize", "route"): "Re-optimized route", ("create", "store"): "Added a store",
    ("learn_location", "store"): "Placed a store on the map", ("login", "user"): "Signed in",
    ("update", "visit"): "Saved visit notes", ("export", "recap"): "Shared a recap",
}


def ago(dt: datetime | None) -> str:
    if not dt:
        return "never"
    secs = (datetime.utcnow() - dt).total_seconds()
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    days = int(secs // 86400)
    return "yesterday" if days == 1 else f"{days} days ago"


def activity(db: Session, user_id: int, limit: int = 8) -> list[dict]:
    rows = db.scalars(select(AuditLog).where(AuditLog.user_id == user_id, AuditLog.action != "login_failed")
                      .order_by(AuditLog.id.desc()).limit(limit * 3)).all()
    out = []
    for r in rows:
        label = ACTIVITY.get((r.action, r.entity))
        if not label:
            continue
        detail = r.detail.split(" gps=")[0] if r.entity == "visit" else r.detail
        if r.action == "login":
            detail = ""
        out.append({"at": r.at, "ago": ago(r.at), "label": label, "detail": detail[:120],
                    "link": f"/visits/{r.entity_id}" if r.entity == "visit" and r.entity_id else None})
        if len(out) == limit:
            break
    return out


def member_summary(db: Session, u: User, today) -> dict:
    from .routes.maps import todays_route
    week_start = today - timedelta(days=today.weekday())
    open_visit = db.scalar(select(Visit).where(Visit.rep_id == u.id, Visit.checked_out_at.is_(None))
                           .order_by(Visit.checked_in_at.desc()))
    if open_visit and open_visit.visit_date != today:
        open_visit = None
    visits_today = db.scalars(select(Visit).where(Visit.rep_id == u.id, Visit.visit_date == today)).all()
    lines_today = [l for v in visits_today for l in v.lines]
    wins_today = sum(len(v.wins) for v in visits_today)
    week_lines = db.scalars(select(AuditLine).join(Visit).where(Visit.rep_id == u.id, Visit.visit_date >= week_start)).all()
    priced = [l for l in week_lines if l.price_check in ("Match", "Over plan", "Under plan")]
    issues = db.scalars(select(Issue).where(Issue.owner_id == u.id, Issue.status != "Resolved")).all()
    route, rv = todays_route(db, u, today)
    last_act = db.scalar(select(func.max(AuditLog.at)).where(AuditLog.user_id == u.id, AuditLog.action != "login_failed"))
    return {
        "u": u, "open_visit": open_visit, "route": route, "route_v": rv,
        "today": {"visits": len(visits_today), "checks": len(lines_today), "wins": wins_today,
                  "issues": sum(1 for l in lines_today if l.discrepancy_type != "None")},
        "week": {"visits": db.scalar(select(func.count(Visit.id)).where(Visit.rep_id == u.id, Visit.visit_date >= week_start)),
                 "wins": db.scalar(select(func.count(Win.id)).join(Visit).where(Win.created_by_id == u.id,
                                                                                Visit.visit_date >= week_start)),
                 "match": (sum(1 for l in priced if l.price_check == "Match") / len(priced)) if priced else None},
        "open": len(issues), "overdue": sum(1 for i in issues if i.due_date and i.due_date < today),
        "tasks": db.scalar(select(func.count(Task.id)).where(Task.assignee_id == u.id, Task.status == "Open")),
        "last_active": last_act, "last_active_ago": ago(last_act),
        "activity": activity(db, u.id, 4),
    }
