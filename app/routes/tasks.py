from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import flash, opt_date, opt_int, redirect, render, s, today
from ..db import get_db
from ..models import Program, Store, Task, User
from ..security import csrf_protect, current_user, log, require_field, require_manager

router = APIRouter()


@router.get("/tasks")
def task_list(request: Request, status: str = "Open", assignee: int | None = None,
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Task)
    if status in ("Open", "Done"):
        stmt = stmt.where(Task.status == status)
    if not user.is_manager and user.role != "viewer":
        stmt = stmt.where(Task.assignee_id == user.id)
    elif assignee:
        stmt = stmt.where(Task.assignee_id == assignee)
    tasks = db.scalars(stmt.order_by(Task.due_date.is_(None), Task.due_date, Task.id.desc()).limit(500)).all()
    team = db.scalars(select(User).where(User.active.is_(True), User.role != "viewer").order_by(User.display_name)).all()
    stores = db.scalars(select(Store).where(Store.active.is_(True)).order_by(Store.chain, Store.store_number)).all() \
        if user.is_manager else []
    progs = db.scalars(select(Program).where(Program.active.is_(True)).order_by(Program.code)).all() \
        if user.is_manager else []
    return render(request, "tasks.html", user=user, tasks=tasks, team=team, stores=stores, progs=progs, t=today(),
                  f={"status": status, "assignee": assignee})


@router.post("/tasks", dependencies=[Depends(csrf_protect)])
async def task_create(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    form = await request.form()
    title = s(form.get("title"))
    if not title:
        raise HTTPException(400, "Give the task a title.")
    try:
        due = opt_date(form.get("due_date"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    ids = [int(x) for x in form.getlist("assignee_id") if s(x).isdigit()]
    if not ids:
        raise HTTPException(400, "Assign the task to at least one person.")
    for aid in ids:
        if not db.get(User, aid):
            continue
        t = Task(title=title, description=s(form.get("description")), assignee_id=aid, due_date=due,
                 program_id=opt_int(form.get("program_id")), store_id=opt_int(form.get("store_id")),
                 created_by_id=user.id)
        db.add(t)
        db.flush()
        log(db, user, "create", "task", t.id, f"{title} -> user {aid}")
    db.commit()
    flash(request, f"Task assigned to {len(ids)} {'person' if len(ids) == 1 else 'people'}.")
    return redirect("/tasks")


@router.post("/tasks/{tid}/done", dependencies=[Depends(csrf_protect)])
async def task_done(tid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    t = db.get(Task, tid)
    if not t:
        raise HTTPException(404)
    if t.assignee_id != user.id and not user.is_manager:
        raise HTTPException(403, "Only the assignee or a manager can complete this task.")
    form = await request.form()
    if t.status == "Open":
        t.status, t.completed_at, t.completion_note = "Done", datetime.utcnow(), s(form.get("note"))
    else:
        t.status, t.completed_at = "Open", None
    log(db, user, "complete" if t.status == "Done" else "reopen", "task", t.id, t.title)
    db.commit()
    flash(request, "Task marked done." if t.status == "Done" else "Task reopened.")
    return redirect(s(form.get("back")) if s(form.get("back")).startswith("/") and not s(form.get("back")).startswith("//") else "/tasks")


@router.post("/tasks/{tid}/delete", dependencies=[Depends(csrf_protect)])
def task_delete(tid: int, request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    t = db.get(Task, tid)
    if not t:
        raise HTTPException(404)
    log(db, user, "delete", "task", t.id, t.title)
    db.delete(t)
    db.commit()
    flash(request, "Task deleted.")
    return redirect("/tasks")
