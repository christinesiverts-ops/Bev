from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import render, today
from ..db import get_db
from ..models import Issue, Task, User, Visit
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
    return render(request, "home.html", user=user, t=t, my_tasks=my_tasks, my_issues=my_issues,
                  my_visits=my_visits, open_visit=open_visit)
