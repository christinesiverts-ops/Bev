"""First-run setup: admin account and plan data from tools/program_data.py."""
import importlib.util
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .models import DataReviewItem, Program, Promo, User
from .security import hash_password, password_problem

log = logging.getLogger("audit.seed")
PROGRAM_DATA = Path(__file__).resolve().parent.parent / "tools" / "program_data.py"


def load_program_data():
    spec = importlib.util.spec_from_file_location("program_data", PROGRAM_DATA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ensure_admin(db: Session) -> None:
    if db.scalar(select(func.count(User.id))):
        return
    if not config.ADMIN_USERNAME or not config.ADMIN_PASSWORD:
        log.warning("No users exist. Set ADMIN_USERNAME and ADMIN_PASSWORD to create the first manager account.")
        return
    problem = password_problem(config.ADMIN_PASSWORD)
    if problem:
        raise SystemExit(f"ADMIN_PASSWORD rejected: {problem}")
    db.add(User(username=config.ADMIN_USERNAME.strip().lower(), display_name=config.ADMIN_USERNAME.strip(),
                role="manager", password_hash=hash_password(config.ADMIN_PASSWORD), must_change_password=True))
    db.commit()
    log.info("Created first manager account '%s' (password change required at first login).", config.ADMIN_USERNAME)


def seed_plan(db: Session) -> None:
    if db.scalar(select(func.count(Program.id))):
        return
    pdat = load_program_data()
    by_code = {}
    for p in pdat.PROGRAMS:
        code = pdat.pid(p["brand"], p["account"])
        prog = Program(code=code, brand=p["brand"], chain=p["chain"], account=p["account"],
                       market=p.get("market", ""), outlets_text=p.get("outlets", ""), total_outlets=p.get("total"),
                       skus=p.get("skus", ""), case_rec=p.get("case_rec", ""), shelf_callout=p.get("shelf", ""),
                       case_cost_text=p.get("case_cost", ""), srp_text=p.get("srp_text", ""), base_price=p.get("base"),
                       timing_text=p.get("timing", ""), priority=p.get("priority", ""), owner=p.get("owner", ""),
                       source=p["source"], data_status=p["status"])
        db.add(prog)
        by_code[code] = prog
    db.flush()
    for (code, sku, typ, offer, unit, case, start, end, disp, src) in pdat.PROMOS:
        db.add(Promo(program_id=by_code[code].id, sku=sku, offer_type=typ, offer=offer, unit_retail=unit,
                     case_cost=case, start=start, end=end, display_required=(disp == "Y"), source=src))
    n_hw = sum(1 for p in pdat.PROGRAMS if p["status"] == pdat.CONFIRM and "HW" in p["source"])
    for acct, brand, issue, action in pdat.DATA_REVIEW:
        db.add(DataReviewItem(account=acct, brand=brand, issue=issue.replace("22 Henry's programs", f"{n_hw} programs"),
                              action=action))
    db.commit()
    log.info("Seeded %d programs and %d promo windows.", len(pdat.PROGRAMS), len(pdat.PROMOS))


def lists():
    pdat = load_program_data()
    return {"discrepancy_types": pdat.DISCREPANCY_TYPES, "skus": pdat.SKU_LIST, "brands": pdat.BRANDS}
