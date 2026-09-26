from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import pricing
from ..common import flash, opt_date, opt_float, opt_int, redirect, render, s, today
from ..db import get_db
from ..models import DATA_STATUSES, AuditLine, DataReviewItem, Issue, Program, Promo, User, Visit
from ..security import csrf_protect, current_user, log, require_manager
from ..seed import lists

router = APIRouter()

PROGRAM_FIELDS = [
    # (form name, label, kind)
    ("brand", "Brand", "brand"), ("chain", "Chain / Banner", "text"), ("account", "Account / Division", "text"),
    ("market", "Market", "text"), ("outlets_text", "Outlets by Market Unit", "text"),
    ("total_outlets", "Total Outlets", "int"), ("skus", "Authorized SKUs / Flavors", "area"),
    ("case_rec", "Case Recommendation", "text"), ("shelf_callout", "Shelf Location / Display Callout", "area"),
    ("case_cost_text", "Case Cost / Frontline", "text"), ("srp_text", "EDV / SRP (text)", "text"),
    ("base_price", "Base Shelf Price ($)", "money"), ("timing_text", "Promo Timing (text)", "text"),
    ("priority", "Execution Priority / Callouts", "area"), ("owner", "Owner", "text"),
    ("source", "Source", "text"), ("data_status", "Data Status", "status"), ("last_verified", "Last Verified", "date"),
]


def program_rows(programs, t):
    rows = []
    for p in programs:
        exp = pricing.expected_price(p, "All", t)
        rows.append({"p": p, "offer": pricing.current_offer_text(p, t), "expected": exp,
                     "next": pricing.next_promo_start(p, t)})
    return rows


@router.get("/plan")
def programs(request: Request, brand: str = "", chain: str = "", status: str = "", q: str = "",
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Program).options(selectinload(Program.promos)).where(Program.active.is_(True))
    if brand:
        stmt = stmt.where(Program.brand == brand)
    if chain:
        stmt = stmt.where(Program.chain == chain)
    if status:
        stmt = stmt.where(Program.data_status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Program.code.ilike(like) | Program.market.ilike(like) | Program.priority.ilike(like))
    progs = db.scalars(stmt.order_by(Program.brand, Program.chain, Program.account)).all()
    chains = db.scalars(select(Program.chain).distinct().order_by(Program.chain)).all()
    return render(request, "plan_list.html", user=user, rows=program_rows(progs, today()), chains=chains,
                  brands=lists()["brands"], statuses=DATA_STATUSES,
                  f={"brand": brand, "chain": chain, "status": status, "q": q})


@router.get("/plan/new")
def program_new(request: Request, user: User = Depends(require_manager)):
    return render(request, "program_form.html", user=user, p=None, fields=PROGRAM_FIELDS,
                  brands=lists()["brands"], statuses=DATA_STATUSES)


def _apply_program(p: Program, form) -> None:
    for name, label, kind in PROGRAM_FIELDS:
        raw = form.get(name)
        try:
            if kind == "int":
                val = opt_int(raw)
            elif kind == "money":
                val = opt_float(raw)
            elif kind == "date":
                val = opt_date(raw)
            else:
                val = s(raw)
        except ValueError as e:
            raise HTTPException(400, f"{label}: {e}")
        setattr(p, name, val)
    if not p.brand or not p.chain or not p.account:
        raise HTTPException(400, "Brand, Chain and Account are required.")
    p.code = f"{p.brand} | {p.account}"


@router.post("/plan/new", dependencies=[Depends(csrf_protect)])
async def program_create(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    form = await request.form()
    p = Program()
    _apply_program(p, form)
    if db.scalar(select(Program).where(Program.code == p.code)):
        raise HTTPException(400, f"A program '{p.code}' already exists.")
    db.add(p)
    db.flush()
    log(db, user, "create", "program", p.id, p.code)
    db.commit()
    flash(request, f"Added {p.code}.")
    return redirect(f"/plan/{p.id}")


@router.get("/plan/{pid}")
def program_detail(pid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Program, pid)
    if not p:
        raise HTTPException(404)
    t = today()
    promos = [(pr, pricing.promo_status(pr, t)) for pr in p.promos]
    recent = db.scalars(select(AuditLine).join(Visit).where(AuditLine.program_id == p.id)
                        .order_by(Visit.checked_in_at.desc()).limit(15)).all()
    open_issues = db.scalars(select(Issue).where(Issue.program_id == p.id, Issue.status != "Resolved")).all()
    return render(request, "program_detail.html", user=user, p=p, promos=promos, t=t,
                  offer=pricing.current_offer_text(p, t), expected=pricing.expected_price(p, "All", t),
                  nxt=pricing.next_promo_start(p, t), sku_prices=pricing.active_sku_prices(p, t), recent=recent, open_issues=open_issues, skus=lists()["skus"])


@router.get("/plan/{pid}/edit")
def program_edit(pid: int, request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    p = db.get(Program, pid)
    if not p:
        raise HTTPException(404)
    return render(request, "program_form.html", user=user, p=p, fields=PROGRAM_FIELDS,
                  brands=lists()["brands"], statuses=DATA_STATUSES)


@router.post("/plan/{pid}/edit", dependencies=[Depends(csrf_protect)])
async def program_update(pid: int, request: Request, user: User = Depends(require_manager),
                         db: Session = Depends(get_db)):
    p = db.get(Program, pid)
    if not p:
        raise HTTPException(404)
    form = await request.form()
    old_code = p.code
    _apply_program(p, form)
    clash = db.scalar(select(Program).where(Program.code == p.code, Program.id != p.id))
    if clash:
        raise HTTPException(400, f"A program '{p.code}' already exists.")
    log(db, user, "update", "program", p.id, old_code if old_code == p.code else f"{old_code} -> {p.code}")
    db.commit()
    flash(request, "Program saved.")
    return redirect(f"/plan/{p.id}")


@router.post("/plan/{pid}/archive", dependencies=[Depends(csrf_protect)])
def program_archive(pid: int, request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    p = db.get(Program, pid)
    if not p:
        raise HTTPException(404)
    p.active = not p.active
    log(db, user, "archive" if not p.active else "restore", "program", p.id, p.code)
    db.commit()
    flash(request, f"{p.code} {'archived' if not p.active else 'restored'}.")
    return redirect("/plan" if not p.active else f"/plan/{p.id}")


# ---- promos ----
def _apply_promo(pr: Promo, form) -> None:
    try:
        pr.sku = s(form.get("sku")) or "All"
        pr.offer_type = s(form.get("offer_type")) or "TPR"
        pr.offer = s(form.get("offer"))
        pr.unit_retail = opt_float(form.get("unit_retail"))
        pr.case_cost = opt_float(form.get("case_cost"))
        pr.start = opt_date(form.get("start"))
        pr.end = opt_date(form.get("end"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    pr.display_required = form.get("display_required") == "Y"
    pr.source = s(form.get("source"))
    if not pr.offer or not pr.start or not pr.end:
        raise HTTPException(400, "Offer, Start and End are required.")
    if pr.end < pr.start:
        raise HTTPException(400, "End date is before start date.")


@router.post("/plan/{pid}/promos", dependencies=[Depends(csrf_protect)])
async def promo_create(pid: int, request: Request, user: User = Depends(require_manager),
                       db: Session = Depends(get_db)):
    p = db.get(Program, pid)
    if not p:
        raise HTTPException(404)
    pr = Promo(program_id=p.id)
    _apply_promo(pr, await request.form())
    db.add(pr)
    db.flush()
    log(db, user, "create", "promo", pr.id, f"{p.code}: {pr.offer} {pr.start}-{pr.end}")
    db.commit()
    flash(request, "Promo window added.")
    return redirect(f"/plan/{p.id}#promos")


@router.get("/promos/{prid}/edit")
def promo_edit(prid: int, request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    pr = db.get(Promo, prid)
    if not pr:
        raise HTTPException(404)
    return render(request, "promo_form.html", user=user, pr=pr, skus=lists()["skus"])


@router.post("/promos/{prid}/edit", dependencies=[Depends(csrf_protect)])
async def promo_update(prid: int, request: Request, user: User = Depends(require_manager),
                       db: Session = Depends(get_db)):
    pr = db.get(Promo, prid)
    if not pr:
        raise HTTPException(404)
    _apply_promo(pr, await request.form())
    log(db, user, "update", "promo", pr.id, f"{pr.program.code}: {pr.offer} {pr.start}-{pr.end}")
    db.commit()
    flash(request, "Promo window saved.")
    return redirect(f"/plan/{pr.program_id}#promos")


@router.post("/promos/{prid}/delete", dependencies=[Depends(csrf_protect)])
def promo_delete(prid: int, request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    pr = db.get(Promo, prid)
    if not pr:
        raise HTTPException(404)
    pid = pr.program_id
    log(db, user, "delete", "promo", pr.id, f"{pr.program.code}: {pr.offer} {pr.start}-{pr.end}")
    db.delete(pr)
    db.commit()
    flash(request, "Promo window deleted.")
    return redirect(f"/plan/{pid}#promos")


@router.get("/calendar")
def calendar(request: Request, status: str = "Active", brand: str = "", user: User = Depends(current_user),
             db: Session = Depends(get_db)):
    t = today()
    rows = []
    for pr in db.scalars(select(Promo).join(Program).where(Program.active.is_(True)).order_by(Promo.start)).all():
        st = pricing.promo_status(pr, t)
        if status and st != status:
            continue
        if brand and pr.program.brand != brand:
            continue
        rows.append((pr, st))
    if status == "Expired":
        rows.reverse()
    return render(request, "calendar.html", user=user, rows=rows, t=t, f={"status": status, "brand": brand},
                  brands=lists()["brands"])


# ---- data review ----
@router.get("/data-review")
def data_review(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(DataReviewItem).order_by(DataReviewItem.resolved, DataReviewItem.id)).all()
    return render(request, "data_review.html", user=user, items=items)


@router.post("/data-review/{iid}", dependencies=[Depends(csrf_protect)])
async def data_review_update(iid: int, request: Request, user: User = Depends(require_manager),
                             db: Session = Depends(get_db)):
    it = db.get(DataReviewItem, iid)
    if not it:
        raise HTTPException(404)
    form = await request.form()
    it.owner = s(form.get("owner"))
    it.resolved = form.get("resolved") == "Y"
    log(db, user, "update", "data_review", it.id, f"resolved={it.resolved} owner={it.owner}")
    db.commit()
    return redirect("/data-review")


@router.post("/data-review", dependencies=[Depends(csrf_protect)])
async def data_review_add(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    form = await request.form()
    if not s(form.get("issue")):
        raise HTTPException(400, "Describe the issue.")
    it = DataReviewItem(account=s(form.get("account")), brand=s(form.get("brand")), issue=s(form.get("issue")),
                        action=s(form.get("action")), owner=s(form.get("owner")))
    db.add(it)
    db.flush()
    log(db, user, "create", "data_review", it.id, it.issue[:200])
    db.commit()
    return redirect("/data-review")
