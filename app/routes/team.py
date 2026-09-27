import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import team as teamlib
from ..common import flash, opt_int, redirect, render, s, today
from ..db import get_db
from ..models import ROLES, Invite, Issue, Task, User, Visit, Win
from ..security import (csrf_protect, current_user_optional, hash_password, ip_blocked, log, login_session,
                        password_problem, record_ip_failure, require_manager)

router = APIRouter()
INVITE_DAYS = 7
USERNAME_OK = set("abcdefghijklmnopqrstuvwxyz0123456789._-")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _members(db, user: User, scope: str):
    stmt = select(User).where(User.active.is_(True), User.role != "viewer")
    if scope == "mine":
        stmt = stmt.where(User.manager_id == user.id)
    else:
        stmt = stmt.where(User.id != user.id)
    return db.scalars(stmt.order_by(User.display_name)).all()


@router.get("/team")
def team_page(request: Request, scope: str = "", user: User = Depends(require_manager), db: Session = Depends(get_db)):
    has_reports = db.scalar(select(User.id).where(User.manager_id == user.id, User.active.is_(True))) is not None
    scope = scope or ("mine" if has_reports else "all")
    t = today()
    members = [teamlib.member_summary(db, u, t) for u in _members(db, user, scope)]
    members.sort(key=lambda m: (m["open_visit"] is None, -(m["today"]["visits"]), m["u"].display_name))
    invites = db.scalars(select(Invite).where(Invite.created_by_id == user.id).order_by(Invite.id.desc()).limit(20)).all()
    return render(request, "team.html", user=user, members=members, scope=scope, t=t, invites=invites,
                  new_link=request.session.pop("new_invite", None), invite_days=INVITE_DAYS)


@router.get("/team/{uid}")
def team_member(uid: int, request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    t = today()
    m = teamlib.member_summary(db, u, t)
    visits = db.scalars(select(Visit).where(Visit.rep_id == u.id).order_by(Visit.checked_in_at.desc()).limit(15)).all()
    issues = db.scalars(select(Issue).where(Issue.owner_id == u.id, Issue.status != "Resolved").order_by(Issue.due_date)).all()
    tasks = db.scalars(select(Task).where(Task.assignee_id == u.id, Task.status == "Open").order_by(Task.due_date)).all()
    wins = db.scalars(select(Win).where(Win.created_by_id == u.id).order_by(Win.created_at.desc()).limit(8)).all()
    days = [t - timedelta(days=i) for i in range(13, -1, -1)]
    per_day = {d: 0 for d in days}
    for v in db.scalars(select(Visit).where(Visit.rep_id == u.id, Visit.visit_date >= days[0])).all():
        per_day[v.visit_date] = per_day.get(v.visit_date, 0) + 1
    return render(request, "team_member.html", user=user, m=m, visits=visits, issues=issues, tasks=tasks, wins=wins,
                  activity=teamlib.activity(db, u.id, 25), per_day=per_day, days=days, t=t,
                  max_day=max(per_day.values()) or 1)


# ---------------- invites ----------------
@router.post("/team/invites", dependencies=[Depends(csrf_protect)])
async def invite_create(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    form = await request.form()
    role = s(form.get("role")) or "rep"
    if role not in ROLES:
        raise HTTPException(400, "Pick a role.")
    token = secrets.token_urlsafe(32)
    inv = Invite(token_hash=_hash(token), role=role, name_hint=s(form.get("name"))[:120], created_by_id=user.id,
                 expires_at=datetime.utcnow() + timedelta(days=INVITE_DAYS))
    db.add(inv)
    db.flush()
    log(db, user, "create", "invite", inv.id, f"role={role} for={inv.name_hint}")
    db.commit()
    from .. import config
    link = (config.PUBLIC_URL or str(request.base_url).rstrip("/")) + f"/join/{token}"
    request.session["new_invite"] = {"link": link, "name": inv.name_hint, "role": role}
    return redirect("/team#invite")


@router.post("/team/invites/{iid}/revoke", dependencies=[Depends(csrf_protect)])
def invite_revoke(iid: int, request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    inv = db.get(Invite, iid)
    if not inv or (inv.created_by_id != user.id and not user.is_manager):
        raise HTTPException(404)
    if inv.state == "Pending":
        inv.revoked_at = datetime.utcnow()
        log(db, user, "revoke", "invite", inv.id, inv.name_hint)
        db.commit()
        flash(request, "Invite link revoked. It no longer works.")
    return redirect("/team#invite")


def _valid_invite(db, token: str) -> Invite | None:
    if not token or len(token) > 100:
        return None
    inv = db.scalar(select(Invite).where(Invite.token_hash == _hash(token)))
    return inv if inv and inv.state == "Pending" else None


@router.get("/join/{token}")
def join_form(token: str, request: Request, user=Depends(current_user_optional), db: Session = Depends(get_db)):
    inv = _valid_invite(db, token)
    if not inv:
        return render(request, "join.html", invalid=True, status_code=410)
    return render(request, "join.html", inv=inv, token=token, current=user)


@router.post("/join/{token}", dependencies=[Depends(csrf_protect)])
async def join_submit(token: str, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    if ip_blocked(ip):
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    inv = _valid_invite(db, token)
    if not inv:
        record_ip_failure(ip)
        return render(request, "join.html", invalid=True, status_code=410)
    form = await request.form()
    name = s(form.get("display_name"))[:120]
    username = s(form.get("username")).lower()
    pw, confirm = str(form.get("password") or ""), str(form.get("confirm") or "")
    error = None
    if not name:
        error = "Enter your name."
    elif not username or not set(username) <= USERNAME_OK or len(username) > 64:
        error = "Username: letters, numbers, dot, dash or underscore only."
    elif db.scalar(select(User).where(User.username == username)):
        error = f"The username '{username}' is taken. Try another."
    elif pw != confirm:
        error = "Passwords don't match."
    else:
        error = password_problem(pw)
    if error:
        return render(request, "join.html", inv=inv, token=token, error=error, form={"display_name": name, "username": username},
                      status_code=400)
    u = User(username=username, display_name=name, role=inv.role, password_hash=hash_password(pw),
             must_change_password=False, manager_id=inv.created_by_id)
    db.add(u)
    db.flush()
    inv.used_at = datetime.utcnow()
    inv.used_by_id = u.id
    log(db, u, "join", "user", u.id, f"via invite {inv.id} from user {inv.created_by_id}")
    db.commit()
    login_session(request, u)
    flash(request, f"Welcome to the team, {name.split(' ')[0]}! You report to {inv.created_by.display_name}.")
    return redirect("/")
