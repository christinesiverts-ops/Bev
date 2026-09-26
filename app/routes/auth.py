from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import flash, redirect, render
from ..db import get_db
from ..models import User
from ..security import (csrf_protect, current_user, current_user_optional, hash_password, ip_blocked, log,
                        login_session, password_problem, record_ip_failure, register_failure, user_locked,
                        verify_password)

router = APIRouter()
GENERIC = "Wrong username or password."


def _safe_next(nxt: str) -> str:
    return nxt if nxt.startswith("/") and not nxt.startswith("//") else "/"


@router.get("/login")
def login_form(request: Request, next: str = "/", user=Depends(current_user_optional)):
    if user:
        return redirect(_safe_next(next))
    return render(request, "login.html", next=_safe_next(next))


@router.post("/login", dependencies=[Depends(csrf_protect)])
def login(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("/"),
          db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    if ip_blocked(ip):
        return render(request, "login.html", next=next, error="Too many attempts. Try again in 15 minutes.",
                      status_code=429)
    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    if user and user.active and user_locked(user):
        return render(request, "login.html", next=next, status_code=423,
                      error="This account is locked for 15 minutes after too many wrong passwords. "
                            "Ask your manager to unlock it.")
    if not user or not user.active or not verify_password(user.password_hash, password):
        record_ip_failure(ip)
        if user and user.active:
            register_failure(user)
            log(db, user, "login_failed", "user", user.id, f"ip={ip}")
            db.commit()
        return render(request, "login.html", next=next, error=GENERIC, status_code=401)
    user.failed_logins = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    log(db, user, "login", "user", user.id, f"ip={ip}")
    db.commit()
    login_session(request, user)
    return redirect("/account/password" if user.must_change_password else _safe_next(next))


@router.post("/logout", dependencies=[Depends(csrf_protect)])
def logout(request: Request):
    request.session.clear()
    return redirect("/login")


@router.get("/account/password")
def pw_form(request: Request, user: User = Depends(current_user)):
    return render(request, "password.html", user=user)


@router.post("/account/password", dependencies=[Depends(csrf_protect)])
def pw_change(request: Request, current: str = Form(...), new: str = Form(...), confirm: str = Form(...),
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    user = db.get(User, user.id)
    error = None
    if not verify_password(user.password_hash, current):
        error = "Current password is wrong."
    elif new != confirm:
        error = "New passwords don't match."
    elif new == current:
        error = "Choose a password different from the current one."
    else:
        error = password_problem(new)
    if error:
        return render(request, "password.html", user=user, error=error, status_code=400)
    user.password_hash = hash_password(new)
    user.must_change_password = False
    user.session_version += 1
    log(db, user, "password_changed", "user", user.id)
    db.commit()
    login_session(request, user)
    flash(request, "Password updated.")
    return redirect("/")
