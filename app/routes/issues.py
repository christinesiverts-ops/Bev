from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import flash, opt_date, opt_int, redirect, render, s, today
from ..db import get_db
from ..models import ISSUE_STATUSES, Issue, IssueUpdate, Program, Store, User
from ..security import csrf_protect, current_user, log, require_field, require_manager
from ..seed import lists

router = APIRouter()


def _team(db):
    return db.scalars(select(User).where(User.active.is_(True), User.role != "viewer").order_by(User.display_name)).all()


@router.get("/issues")
def issue_list(request: Request, status: str = "open", owner: int | None = None, brand: str = "", dtype: str = "",
               overdue: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Issue)
    if status == "open":
        stmt = stmt.where(Issue.status != "Resolved")
    elif status in ISSUE_STATUSES:
        stmt = stmt.where(Issue.status == status)
    if owner:
        stmt = stmt.where(Issue.owner_id == owner)
    if dtype:
        stmt = stmt.where(Issue.discrepancy_type == dtype)
    if brand:
        stmt = stmt.join(Program, Issue.program_id == Program.id).where(Program.brand == brand)
    if overdue:
        stmt = stmt.where(Issue.status != "Resolved", Issue.due_date < today())
    issues = db.scalars(stmt.order_by(Issue.due_date.is_(None), Issue.due_date, Issue.id.desc()).limit(500)).all()
    L = lists()
    return render(request, "issues.html", user=user, issues=issues, team=_team(db), brands=L["brands"],
                  dtypes=L["discrepancy_types"][1:], t=today(),
                  f={"status": status, "owner": owner, "brand": brand, "dtype": dtype, "overdue": overdue})


@router.get("/issues/new")
def issue_new(request: Request, store_id: int | None = None, user: User = Depends(require_manager),
              db: Session = Depends(get_db)):
    stores = db.scalars(select(Store).where(Store.active.is_(True)).order_by(Store.chain, Store.store_number)).all()
    progs = db.scalars(select(Program).where(Program.active.is_(True)).order_by(Program.code)).all()
    return render(request, "issue_new.html", user=user, stores=stores, progs=progs, team=_team(db),
                  dtypes=lists()["discrepancy_types"][1:], store_id=store_id)


@router.post("/issues/new", dependencies=[Depends(csrf_protect)])
async def issue_create(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    form = await request.form()
    st = db.get(Store, opt_int(form.get("store_id")) or 0)
    if not st:
        raise HTTPException(400, "Pick a store.")
    try:
        due = opt_date(form.get("due_date"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    iss = Issue(store_id=st.id, program_id=opt_int(form.get("program_id")), discrepancy_type=s(form.get("discrepancy_type")) or "Other",
                description=s(form.get("description")), action=s(form.get("action")),
                owner_id=opt_int(form.get("owner_id")), due_date=due, created_by_id=user.id)
    db.add(iss)
    db.flush()
    db.add(IssueUpdate(issue_id=iss.id, user_id=user.id, status="Open", note="Raised by manager"))
    log(db, user, "create", "issue", iss.id, f"{st.label}: {iss.discrepancy_type}")
    db.commit()
    flash(request, f"Follow-up #{iss.id} created.")
    return redirect(f"/issues/{iss.id}")


@router.get("/issues/{iid}")
def issue_detail(iid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    iss = db.get(Issue, iid)
    if not iss:
        raise HTTPException(404)
    photos = []
    if iss.audit_line_id:
        from ..models import AuditLine
        line = db.get(AuditLine, iss.audit_line_id)
        photos = line.photos if line else []
    return render(request, "issue_detail.html", user=user, iss=iss, photos=photos, statuses=ISSUE_STATUSES,
                  team=_team(db), t=today())


@router.post("/issues/{iid}/update", dependencies=[Depends(csrf_protect)])
async def issue_update(iid: int, request: Request, user: User = Depends(require_field), db: Session = Depends(get_db)):
    iss = db.get(Issue, iid)
    if not iss:
        raise HTTPException(404)
    form = await request.form()
    status = s(form.get("status")) or iss.status
    if status not in ISSUE_STATUSES:
        raise HTTPException(400, "Unknown status.")
    note = s(form.get("note"))
    changes = []
    if user.is_manager:
        owner_id = opt_int(form.get("owner_id"))
        if owner_id and owner_id != iss.owner_id:
            iss.owner_id = owner_id
            changes.append("owner changed")
        try:
            due = opt_date(form.get("due_date"))
        except ValueError as e:
            raise HTTPException(400, str(e))
        if due and due != iss.due_date:
            iss.due_date = due
            changes.append(f"due {due:%m/%d}")
        if s(form.get("action")) != iss.action and "action" in form:
            iss.action = s(form.get("action"))
    if status == "Resolved" and not note:
        raise HTTPException(400, "Add a note saying how it was resolved.")
    if status != iss.status:
        changes.append(f"{iss.status} -> {status}")
        iss.status = status
        iss.resolved_at = datetime.utcnow() if status == "Resolved" else None
    if not changes and not note:
        return redirect(f"/issues/{iss.id}")
    db.add(IssueUpdate(issue_id=iss.id, user_id=user.id, status=iss.status,
                       note="; ".join(filter(None, [note, ", ".join(changes) if changes else ""]))))
    log(db, user, "update", "issue", iss.id, ", ".join(changes) or "note")
    db.commit()
    flash(request, "Follow-up updated.")
    back = s(form.get("back"))
    return redirect(back if back.startswith("/") and not back.startswith("//") else f"/issues/{iss.id}")
