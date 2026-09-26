"""Password hashing, sessions, CSRF, login throttling and role checks."""
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .models import AuditLog, User

_ph = PasswordHasher()


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(hash_: str, pw: str) -> bool:
    try:
        return _ph.verify(hash_, pw)
    except (VerificationError, InvalidHashError):
        return False


def password_problem(pw: str) -> str | None:
    if len(pw) < config.MIN_PASSWORD_LEN:
        return f"Password must be at least {config.MIN_PASSWORD_LEN} characters."
    if pw.lower() == pw or pw.upper() == pw or not any(c.isdigit() for c in pw):
        return "Use upper- and lower-case letters and at least one number."
    return None


def temp_password() -> str:
    # readable, meets policy: e.g. "Kx7p-Qm4t-Za9w"
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz"
    parts = ["".join(secrets.choice(alphabet) for _ in range(3)) + secrets.choice("23456789") for _ in range(3)]
    return "-".join(parts)


# ---- login throttling per client IP (in-memory; single container) ----
_ip_attempts: dict[str, deque] = defaultdict(deque)
IP_WINDOW_S = 900
IP_MAX_ATTEMPTS = 20


def ip_blocked(ip: str) -> bool:
    q = _ip_attempts[ip]
    now = time.monotonic()
    while q and now - q[0] > IP_WINDOW_S:
        q.popleft()
    return len(q) >= IP_MAX_ATTEMPTS


def record_ip_failure(ip: str) -> None:
    _ip_attempts[ip].append(time.monotonic())


def reset_throttle() -> None:
    _ip_attempts.clear()


def user_locked(user: User) -> bool:
    return bool(user.locked_until and user.locked_until > datetime.utcnow())


def register_failure(user: User) -> None:
    user.failed_logins += 1
    if user.failed_logins >= config.MAX_LOGIN_FAILURES:
        user.locked_until = datetime.utcnow() + timedelta(minutes=config.LOCKOUT_MINUTES)
        user.failed_logins = 0


# ---- sessions ----
def login_session(request: Request, user: User) -> None:
    request.session.clear()
    request.session["uid"] = user.id
    request.session["sv"] = user.session_version
    request.session["csrf"] = secrets.token_urlsafe(32)


def csrf_token(request: Request) -> str:
    tok = request.session.get("csrf")
    if not tok:
        tok = secrets.token_urlsafe(32)
        request.session["csrf"] = tok
    return tok


class LoginRequired(Exception):
    pass


class PasswordChangeRequired(Exception):
    pass


def current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    uid = request.session.get("uid")
    if not uid:
        return None
    user = db.get(User, uid)
    if not user or not user.active or request.session.get("sv") != user.session_version:
        request.session.clear()
        return None
    return user


def current_user(request: Request, user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise LoginRequired()
    if user.must_change_password and request.url.path not in ("/account/password", "/logout"):
        raise PasswordChangeRequired()
    return user


def require_manager(user: User = Depends(current_user)) -> User:
    if not user.is_manager:
        raise HTTPException(status_code=403, detail="Managers only.")
    return user


def require_field(user: User = Depends(current_user)) -> User:
    if not user.can_log_visits:
        raise HTTPException(status_code=403, detail="Your account is view-only.")
    return user


async def csrf_protect(request: Request) -> None:
    """Dependency for every state-changing route."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    form = await request.form()
    sent = form.get("csrf_token") or request.headers.get("x-csrf-token")
    expected = request.session.get("csrf")
    if not expected or not sent or not secrets.compare_digest(str(sent), expected):
        raise HTTPException(status_code=403, detail="Form expired or invalid. Go back, refresh the page and try again.")


def log(db: Session, user: User | None, action: str, entity: str, entity_id: int | None = None, detail: str = "") -> None:
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id,
                    detail=detail[:2000]))
