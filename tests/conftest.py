import io
import os
import re
import tempfile
from datetime import date

import pytest

_TMP = tempfile.mkdtemp(prefix="audit-test-")
os.environ.update(DATA_DIR=_TMP, SECRET_KEY="t" * 64, COOKIE_SECURE="false", ADMIN_USERNAME="boss",
                  ADMIN_PASSWORD="Initial-Pass-1", BACKUPS_ENABLED="false")

from fastapi.testclient import TestClient  # noqa: E402

from app import db as app_db  # noqa: E402
from app import security  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import User  # noqa: E402

FIXED_TODAY = date(2026, 9, 26)
CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def csrf(client, path="/"):
    r = client.get(path)
    m = CSRF_RE.search(r.text)
    assert m, f"no csrf token on {path}: {r.status_code}"
    return m.group(1)


def post(client, path, data=None, files=None, page=None, **kw):
    data = dict(data or {})
    data["csrf_token"] = csrf(client, page or "/")
    return client.post(path, data=data, files=files, follow_redirects=kw.get("follow", False))


def login(client, username, password):
    return post(client, "/login", {"username": username, "password": password}, page="/login")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("app.config.DB_PATH", tmp_path / "audit.db")
    monkeypatch.setattr("app.config.PHOTO_DIR", tmp_path / "photos")
    monkeypatch.setattr("app.config.BACKUP_DIR", tmp_path / "backups")
    for mod in ("app.common", "app.routes.visits", "app.routes.home", "app.routes.plan", "app.routes.stores",
                "app.routes.issues", "app.routes.tasks", "app.routes.dashboard"):
        monkeypatch.setattr(f"{mod}.today", lambda: FIXED_TODAY)
    security.reset_throttle()
    application = create_app(db_url=f"sqlite:///{tmp_path / 'audit.db'}", start_background=False)
    return application


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


def make_user(username, role, password="Field-Pass-99"):
    with app_db.SessionLocal() as s:
        s.add(User(username=username, display_name=username.title(), role=role,
                   password_hash=security.hash_password(password), must_change_password=False))
        s.commit()
    return password


@pytest.fixture()
def manager(client):
    login(client, "boss", "Initial-Pass-1")
    r = post(client, "/account/password", {"current": "Initial-Pass-1", "new": "Manager-Pass-2", "confirm": "Manager-Pass-2"},
             page="/account/password")
    assert r.status_code == 303
    return client


@pytest.fixture()
def other(app):
    """A second, independent browser session."""
    with TestClient(app) as c:
        yield c


def jpeg_bytes(color="red"):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), color).save(buf, "JPEG")
    return buf.getvalue()
