from app import db as app_db
from app.models import User
from tests.conftest import csrf, login, make_user, post


def test_first_login_forces_password_change(client):
    r = login(client, "boss", "Initial-Pass-1")
    assert r.headers["location"] == "/account/password"
    assert client.get("/plan", follow_redirects=False).headers["location"] == "/account/password"
    bad = post(client, "/account/password", {"current": "Initial-Pass-1", "new": "short", "confirm": "short"},
               page="/account/password")
    assert bad.status_code == 400
    ok = post(client, "/account/password", {"current": "Initial-Pass-1", "new": "Better-Pass-77", "confirm": "Better-Pass-77"},
              page="/account/password")
    assert ok.status_code == 303
    assert client.get("/plan").status_code == 200


def test_wrong_password_and_lockout(client):
    make_user("rep1", "rep")
    for _ in range(5):
        assert login(client, "rep1", "nope-nope-nope").status_code == 401
    r = login(client, "rep1", "Field-Pass-99")
    assert r.status_code == 423
    with app_db.SessionLocal() as s:
        assert s.query(User).filter_by(username="rep1").one().locked_until is not None


def test_unknown_user_generic_error(client):
    r = login(client, "ghost", "whatever-123")
    assert r.status_code == 401 and "Wrong username or password" in r.text


def test_csrf_required(client):
    make_user("rep1", "rep")
    login(client, "rep1", "Field-Pass-99")
    r = client.post("/logout", data={"csrf_token": "forged"})
    assert r.status_code == 403
    r = client.post("/logout", data={})
    assert r.status_code == 403
    assert csrf(client)  # still signed in


def test_pages_require_login(client):
    for path in ("/", "/plan", "/stores", "/dashboard", "/photos/1", "/data/export.xlsx", "/admin/users"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/login"), path


def test_security_headers(client):
    r = client.get("/login")
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in r.headers["content-security-policy"]


def test_session_killed_when_deactivated(client, other):
    make_user("rep1", "rep")
    login(other, "rep1", "Field-Pass-99")
    assert other.get("/", follow_redirects=False).status_code == 200
    with app_db.SessionLocal() as s:
        u = s.query(User).filter_by(username="rep1").one()
        u.active = False
        u.session_version += 1
        s.commit()
    assert other.get("/", follow_redirects=False).status_code == 303
