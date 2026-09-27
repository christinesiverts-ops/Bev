import itertools
import re
from datetime import datetime, timedelta

from sqlalchemy import select

from app import db as app_db
from app import routing
from app.models import Invite, Route, Store, User, Visit
from tests.conftest import FIXED_TODAY, jpeg_bytes, login, make_user, post
from tests.test_workflow import add_store, check_in, pid


def uid(username):
    with app_db.SessionLocal() as s:
        return s.scalar(select(User.id).where(User.username == username))


# ---------------- routing ----------------
def test_optimize_matches_brute_force():
    pts = [(45.52, -122.68), (45.50, -122.60), (45.60, -122.70), (45.51, -122.67), (45.45, -122.80), (45.55, -122.50)]
    start = (45.53, -122.69)
    order = routing.optimize(pts, start)
    assert sorted(order) == list(range(len(pts)))
    best = min(routing._path_len(pts, list(p), start) for p in itertools.permutations(range(len(pts))))
    assert routing._path_len(pts, order, start) <= best * 1.02


def test_google_links_are_chunked():
    pts = [(45.0 + i / 100, -122.0) for i in range(20)]
    links = routing.google_maps_links(pts, (44.9, -122.0))
    assert len(links) == 2 and all(l.count("%7C") <= 8 for l in links)
    assert "origin=44.900000" in links[0] and "origin=45.090000" in links[1]


# ---------------- map + routes ----------------
def test_store_location_learned_on_first_accurate_checkin(manager):
    r = post(manager, "/stores/new", {"chain": "WinCo Foods", "store_number": "88", "city": "Salem"}, page="/stores/new")
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    check_in(manager, sid, lat="44.9429", lng="-123.0351")
    with app_db.SessionLocal() as s:
        st = s.get(Store, sid)
        assert (st.lat, st.lng) == (44.9429, -123.0351)


def test_map_and_route_flow(manager, other):
    a = add_store(manager, chain="WinCo Foods", number="1", lat="45.52", lng="-122.68")
    b = add_store(manager, chain="WinCo Foods", number="2", lat="45.60", lng="-122.70")
    c = add_store(manager, chain="WinCo Foods", number="3", lat="45.51", lng="-122.67")
    assert manager.get("/map").status_code == 200
    data = manager.get("/map/stores.json").json()
    assert {d["id"] for d in data} == {a, b, c} and all(d["level"] == "due" for d in data)   # never visited
    make_user("rep1", "rep")
    rep_id = uid("rep1")
    # manager plans and assigns a route to the rep, starting near store a
    r = post(manager, "/routes", [("store_id", str(b)), ("store_id", str(c)), ("store_id", str(a)),
                                  ("assignee_id", str(rep_id)), ("route_date", FIXED_TODAY.isoformat()),
                                  ("start_lat", "45.521"), ("start_lng", "-122.681")], page="/map")
    assert r.status_code == 303
    rid = int(r.headers["location"].rsplit("/", 1)[1])
    with app_db.SessionLocal() as s:
        route = s.get(Route, rid)
        assert route.assignee_id == rep_id
        assert [st.store_id for st in route.stops] == [a, c, b]        # nearest-first from the start point
        assert "never visited" in route.stops[0].reason
    login(other, "rep1", "Field-Pass-99")
    home = other.get("/").text
    assert "Today's route" in home and "Next stop" in home
    page = other.get(f"/routes/{rid}").text
    assert "Navigate" in page and "google.com/maps/dir" in page
    # visiting the first stop marks it done and moves "next" on
    check_in(other, a, lat="45.52", lng="-122.68")
    with app_db.SessionLocal() as s:
        from app.routes.maps import route_view
        v = route_view(s, s.get(Route, rid))
        assert v["done"] == 1 and v["next"]["stop"].store_id == c
    # rep can reorder / remove on their own route
    with app_db.SessionLocal() as s:
        last = s.get(Route, rid).stops[-1].id
    assert post(other, f"/routes/{rid}/stops/{last}", {"action": "up"}, page=f"/routes/{rid}").status_code == 303
    assert post(other, f"/routes/{rid}/optimize", {"lat": "45.50", "lng": "-122.60"}, page=f"/routes/{rid}").status_code == 303
    assert post(other, f"/routes/{rid}/stops/{last}", {"action": "remove"}, page=f"/routes/{rid}").status_code == 303
    with app_db.SessionLocal() as s:
        assert len(s.get(Route, rid).stops) == 2


def test_rep_routes_are_their_own(manager, other):
    a = add_store(manager, number="10")
    make_user("rep1", "rep")
    make_user("rep2", "rep")
    login(other, "rep1", "Field-Pass-99")
    r = post(other, "/routes", [("store_id", str(a)), ("assignee_id", str(uid("rep2")))], page="/map")
    rid = int(r.headers["location"].rsplit("/", 1)[1])
    with app_db.SessionLocal() as s:
        assert s.get(Route, rid).assignee_id == uid("rep1")          # reps can't assign to others
    post(other, "/logout")
    login(other, "rep2", "Field-Pass-99")
    assert other.get(f"/routes/{rid}").status_code == 403
    assert post(other, f"/routes/{rid}/delete", page="/").status_code == 403


def test_geocode_job(manager, monkeypatch):
    from app import geocode
    add_store(manager, number="20", lat="", lng="", address="1 Main St", zip="93721")
    monkeypatch.setattr(geocode, "lookup", lambda q: (36.73, -119.78))
    monkeypatch.setattr(geocode.time, "sleep", lambda s: None)
    started = []
    monkeypatch.setattr(geocode.threading, "Thread", lambda target, args, **kw: type("T", (), {"start": lambda self: started.append(target(*args))})())
    assert post(manager, "/map/geocode", page="/map").status_code == 303
    with app_db.SessionLocal() as s:
        st = s.scalar(select(Store).where(Store.store_number == "20"))
        assert (st.lat, st.lng) == (36.73, -119.78)


# ---------------- recaps ----------------
def test_visit_recap_and_pdf(manager):
    sid = add_store(manager)
    vid = check_in(manager, sid)
    post(manager, f"/visits/{vid}/lines", {"program_id": pid("ZOA | Smart & Final"), "sku": "Singles (Frosted Grape/Tropical Punch)",
                                           "observed_price": "1.79", "notes": "tag missing"},
         files=[("photos", ("a.jpg", jpeg_bytes(), "image/jpeg"))], page=f"/visits/{vid}")
    post(manager, f"/visits/{vid}/wins", {"win_type": "New display", "brand": "ZOA", "cases": "25"}, page=f"/visits/{vid}")
    post(manager, f"/visits/{vid}/notes", {"notes": "SM Dana is out until Friday - internal"}, page=f"/visits/{vid}")
    r = post(manager, f"/visits/{vid}/checkout", page=f"/visits/{vid}")
    assert r.headers["location"] == f"/visits/{vid}/recap"
    team = manager.get(f"/visits/{vid}/recap").text
    assert "Over plan" in team and "New display" in team and "SM Dana" in team
    store_copy = manager.get(f"/visits/{vid}/recap?audience=store").text
    assert "SM Dana" not in store_copy and "Over plan" in store_copy
    pdf = manager.get(f"/visits/{vid}/recap.pdf")
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-" and pdf.headers["content-type"] == "application/pdf"
    assert len(manager.get(f"/visits/{vid}/recap.pdf?audience=store&photos=0").content) < len(pdf.content)
    day = manager.get("/recap/day").text
    assert "Smart &amp; Final" in day
    assert manager.get(f"/recap/day.pdf?day={FIXED_TODAY.isoformat()}").content[:5] == b"%PDF-"


# ---------------- team + invites ----------------
def test_invite_signup_puts_member_under_manager(manager, other):
    r = post(manager, "/team/invites", {"name": "Casey Morgan", "role": "rep"}, page="/team")
    assert r.status_code == 303
    page = manager.get("/team").text
    link = re.search(r'value="(http[^"]+/join/[^"]+)"', page).group(1)
    assert "/join/" in link and "Casey Morgan" in page
    assert re.search(r'value="(http[^"]+/join/[^"]+)"', manager.get("/team").text) is None   # shown once
    path = link.split("testserver", 1)[1]
    form = other.get(path)
    assert form.status_code == 200 and "Join" in form.text and 'value="Casey Morgan"' in form.text
    bad = post(other, path, {"display_name": "Casey Morgan", "username": "cmorgan", "password": "short", "confirm": "short"}, page=path)
    assert bad.status_code == 400
    ok = post(other, path, {"display_name": "Casey Morgan", "username": "cmorgan", "password": "Casey-Pass-2026",
                            "confirm": "Casey-Pass-2026"}, page=path)
    assert ok.status_code == 303
    assert "Welcome to the team" in other.get("/").text
    with app_db.SessionLocal() as s:
        u = s.scalar(select(User).where(User.username == "cmorgan"))
        boss = s.scalar(select(User).where(User.username == "boss"))
        assert u.manager_id == boss.id and u.role == "rep" and not u.must_change_password
    assert other.get(path).status_code == 410                      # single use
    team = manager.get("/team?scope=mine").text
    assert "Casey Morgan" in team
    assert manager.get(f"/team/{u.id}").status_code == 200


def test_invite_expiry_revoke_and_permissions(manager, other):
    post(manager, "/team/invites", {"role": "rep"}, page="/team")
    link = re.search(r'value="(http[^"]+/join/[^"]+)"', manager.get("/team").text).group(1)
    path = link.split("testserver", 1)[1]
    with app_db.SessionLocal() as s:
        inv = s.scalar(select(Invite).order_by(Invite.id.desc()))
        inv.expires_at = datetime.utcnow() - timedelta(minutes=1)
        s.commit()
    assert other.get(path).status_code == 410
    post(manager, "/team/invites", {"role": "rep"}, page="/team")
    link2 = re.search(r'value="(http[^"]+/join/[^"]+)"', manager.get("/team").text).group(1)
    with app_db.SessionLocal() as s:
        inv2 = s.scalar(select(Invite).order_by(Invite.id.desc()))
    post(manager, f"/team/invites/{inv2.id}/revoke", page="/team")
    assert other.get(link2.split("testserver", 1)[1]).status_code == 410
    assert other.get("/join/not-a-real-token").status_code == 410
    make_user("rep1", "rep")
    login(other, "rep1", "Field-Pass-99")
    assert other.get("/team").status_code == 403
    assert post(other, "/team/invites", {"role": "manager"}, page="/").status_code == 403


def test_team_shows_who_is_in_store(manager, other):
    sid = add_store(manager)
    make_user("rep1", "rep")
    login(other, "rep1", "Field-Pass-99")
    check_in(other, sid)
    page = manager.get("/team?scope=all").text
    assert "In store now" in page and "Checked in" in page
