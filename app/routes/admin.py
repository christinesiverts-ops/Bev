from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..common import flash, redirect, render, s
from ..db import get_db
from ..models import ROLES, AuditLog, User
from ..security import csrf_protect, hash_password, log, require_manager, temp_password

router = APIRouter(prefix="/admin")
USERNAME_OK = set("abcdefghijklmnopqrstuvwxyz0123456789._-")


def _active_managers(db) -> int:
    return db.scalar(select(func.count(User.id)).where(User.role == "manager", User.active.is_(True)))


@router.get("/users")
def users(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    people = db.scalars(select(User).order_by(User.active.desc(), User.display_name)).all()
    return render(request, "admin_users.html", user=user, people=people, roles=ROLES, now=datetime.utcnow(),
                  new_pw=request.session.pop("new_pw", None))


@router.post("/users", dependencies=[Depends(csrf_protect)])
async def user_create(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    form = await request.form()
    username = s(form.get("username")).lower()
    display = s(form.get("display_name")) or username
    role = s(form.get("role"))
    if not username or not set(username) <= USERNAME_OK or len(username) > 64:
        raise HTTPException(400, "Username: letters, numbers, dot, dash or underscore only.")
    if role not in ROLES:
        raise HTTPException(400, "Pick a role.")
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(400, f"Username '{username}' is taken.")
    pw = temp_password()
    u = User(username=username, display_name=display, role=role, password_hash=hash_password(pw),
             must_change_password=True)
    db.add(u)
    db.flush()
    log(db, user, "create", "user", u.id, f"{username} role={role}")
    db.commit()
    request.session["new_pw"] = [u.display_name, u.username, pw]
    return redirect("/admin/users")


@router.post("/users/{uid}", dependencies=[Depends(csrf_protect)])
async def user_update(uid: int, request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    form = await request.form()
    action = s(form.get("action"))
    if action == "save":
        role = s(form.get("role"))
        active = form.get("active") == "Y"
        if role not in ROLES:
            raise HTTPException(400, "Pick a role.")
        losing_manager = u.role == "manager" and u.active and (role != "manager" or not active)
        if losing_manager and _active_managers(db) <= 1:
            raise HTTPException(400, "You can't remove the last active manager.")
        changes = []
        if role != u.role:
            changes.append(f"role {u.role}->{role}")
        if active != u.active:
            changes.append("activated" if active else "deactivated")
            u.session_version += 1  # sign out everywhere
        u.role, u.active = role, active
        u.display_name = s(form.get("display_name")) or u.display_name
        log(db, user, "update", "user", u.id, ", ".join(changes) or "name")
        flash(request, f"Saved {u.display_name}.")
    elif action == "reset":
        pw = temp_password()
        u.password_hash = hash_password(pw)
        u.must_change_password = True
        u.session_version += 1
        u.failed_logins, u.locked_until = 0, None
        log(db, user, "reset_password", "user", u.id, u.username)
        request.session["new_pw"] = [u.display_name, u.username, pw]
    elif action == "unlock":
        u.failed_logins, u.locked_until = 0, None
        log(db, user, "unlock", "user", u.id, u.username)
        flash(request, f"Unlocked {u.display_name}.")
    else:
        raise HTTPException(400, "Unknown action.")
    db.commit()
    return redirect("/admin/users")


@router.get("/log")
def audit_log(request: Request, page: int = 1, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    page = max(page, 1)
    per = 100
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset((page - 1) * per).limit(per + 1)).all()
    return render(request, "admin_log.html", user=user, rows=rows[:per], page=page, more=len(rows) > per)
