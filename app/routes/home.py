from fastapi import APIRouter, Depends, Request
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..common import render, today
from ..db import get_db
from ..models import Issue, Store, Task, User, Visit, Win
from ..security import current_user

router = APIRouter()


@router.get("/")
def home(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = today()
    my_tasks = db.scalars(select(Task).where(Task.assignee_id == user.id, Task.status == "Open")
                          .order_by(Task.due_date.is_(None), Task.due_date)).all()
    my_issues = db.scalars(select(Issue).where(Issue.owner_id == user.id, Issue.status != "Resolved")
                           .order_by(Issue.due_date.is_(None), Issue.due_date)).all()
    my_visits = db.scalars(select(Visit).where(Visit.rep_id == user.id)
                           .order_by(Visit.checked_in_at.desc()).limit(8)).all()
    open_visit = next((v for v in my_visits if v.checked_out_at is None), None)
    week_start = t - timedelta(days=t.weekday())
    month_start = t.replace(day=1)
    stats = {
        "visits_week": db.scalar(select(func.count(Visit.id)).where(Visit.rep_id == user.id, Visit.visit_date >= week_start)),
        "wins_month": db.scalar(select(func.count(Win.id)).join(Visit).where(Win.created_by_id == user.id,
                                                                              Visit.visit_date >= month_start)),
        "open": len(my_issues),
        "overdue": sum(1 for i in my_issues if i.due_date and i.due_date < t),
        "tasks": len(my_tasks),
    }
    recent_ids = []
    for sid, in db.execute(select(Visit.store_id).where(Visit.rep_id == user.id)
                           .order_by(Visit.checked_in_at.desc()).limit(40)).all():
        if sid not in recent_ids:
            recent_ids.append(sid)
        if len(recent_ids) == 6:
            break
    recent_stores = [db.get(Store, i) for i in recent_ids]
    team = None
    if user.is_manager:
        team = {
            "visits_week": db.scalar(select(func.count(Visit.id)).where(Visit.visit_date >= week_start)),
            "wins_week": db.scalar(select(func.count(Win.id)).join(Visit).where(Visit.visit_date >= week_start)),
            "open": db.scalar(select(func.count(Issue.id)).where(Issue.status != "Resolved")),
            "overdue": db.scalar(select(func.count(Issue.id)).where(Issue.status != "Resolved", Issue.due_date < t)),
        }
    recent_wins = db.scalars(select(Win).order_by(Win.created_at.desc()).limit(5)).all()
    from .maps import todays_route
    route, route_v = todays_route(db, user, t)
    return render(request, "home.html", user=user, t=t, route=route, route_v=route_v, my_tasks=my_tasks, my_issues=my_issues,
                  my_visits=my_visits, open_visit=open_visit, stats=stats, recent_stores=recent_stores,
                  team=team, recent_wins=recent_wins)
