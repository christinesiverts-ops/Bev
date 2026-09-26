"""Excel export of everything, and plan import from the Chain Audit Tool workbook (or a previous export)."""
import io
from datetime import date, datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLine, DataReviewItem, Issue, Program, Promo, Store, Task, Visit
from .common import local_dt

# Column names match the Chain Audit Tool workbook so exports can be re-imported.
PROGRAM_COLS = [
    ("Program ID", "code"), ("Brand", "brand"), ("Chain / Banner", "chain"), ("Account / Division", "account"),
    ("Market", "market"), ("Outlets by Market Unit", "outlets_text"), ("Total Outlets", "total_outlets"),
    ("Authorized SKUs / Flavors", "skus"), ("Case Recommendation", "case_rec"),
    ("Shelf Location / Display Callout", "shelf_callout"), ("Case Cost / Frontline", "case_cost_text"),
    ("EDV / SRP", "srp_text"), ("Base Shelf Price ($)", "base_price"), ("Promo Timing", "timing_text"),
    ("Execution Priority / Callouts", "priority"), ("Owner", "owner"), ("Source", "source"),
    ("Data Status", "data_status"), ("Last Verified", "last_verified"),
]
PROMO_COLS = [("Program ID", None), ("SKU / Pack", "sku"), ("Offer Type", "offer_type"), ("Offer", "offer"),
              ("Unit Retail ($)", "unit_retail"), ("Case Cost ($)", "case_cost"), ("Start", "start"), ("End", "end"),
              ("Display Required", "display_required"), ("Source", "source")]

HEAD_FILL = PatternFill("solid", start_color="1F2A44", end_color="1F2A44")


def _sheet(wb, title, headers, rows, widths=None):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(c)].width = (widths or {}).get(c, 18)
    for r in rows:
        ws.append(r)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Arial", size=10)
            if isinstance(cell.value, (date, datetime)):
                cell.number_format = "m/d/yyyy" if isinstance(cell.value, date) and not isinstance(cell.value, datetime) else "m/d/yyyy h:mm"
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def _yn(b):
    return "" if b is None else ("Y" if b else "N")


def export_workbook(db: Session) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    progs = db.scalars(select(Program).order_by(Program.brand, Program.chain, Program.account)).all()
    _sheet(wb, "Chain Program", [h for h, _ in PROGRAM_COLS] + ["Active"],
           [[getattr(p, a) for _, a in PROGRAM_COLS] + [_yn(p.active)] for p in progs], {1: 34, 15: 50})
    promos = db.scalars(select(Promo).join(Program).order_by(Program.code, Promo.start)).all()
    _sheet(wb, "Promo Calendar", [h for h, _ in PROMO_COLS],
           [[pr.program.code] + [(_yn(getattr(pr, a)) if a == "display_required" else getattr(pr, a))
                                 for _, a in PROMO_COLS[1:]] for pr in promos], {1: 34, 4: 30})
    stores = db.scalars(select(Store).order_by(Store.chain, Store.store_number)).all()
    _sheet(wb, "Stores", ["Chain", "Division", "Store #", "Name", "Address", "City", "State", "Zip", "Market Unit",
                          "Lat", "Lng", "Verified", "Active"],
           [[s.chain, s.division, s.store_number, s.name, s.address, s.city, s.state, s.zip, s.market_unit, s.lat,
             s.lng, _yn(s.verified), _yn(s.active)] for s in stores])
    lines = db.scalars(select(AuditLine).join(Visit).order_by(Visit.checked_in_at, AuditLine.id)).all()
    _sheet(wb, "Visit Checks", ["Visit ID", "Visit Date", "Rep", "Chain", "Store #", "City", "Checked In", "GPS Distance (m)",
                                "Program ID", "SKU", "Expected Price", "Expected Basis", "Observed Price", "Price Check",
                                "Shelf Tag OK", "Planogram OK", "In Stock", "Display per Callout", "Discrepancy",
                                "Notes", "Photos"],
           [[l.visit.id, l.visit.visit_date, l.visit.rep.display_name, l.visit.store.chain, l.visit.store.store_number,
             l.visit.store.city, local_dt(l.visit.checked_in_at), l.visit.distance_m, l.program.code, l.sku,
             l.expected_price, l.expected_basis, l.observed_price, l.price_check, _yn(l.tag_ok), _yn(l.planogram_ok),
             _yn(l.in_stock_ok), l.display, l.discrepancy_type, l.notes, len(l.photos)] for l in lines], {20: 50})
    visits = db.scalars(select(Visit).order_by(Visit.checked_in_at)).all()
    _sheet(wb, "Visits", ["Visit ID", "Visit Date", "Rep", "Chain", "Store #", "City", "Checked In", "Checked Out",
                          "GPS Distance (m)", "Checks", "Visit Notes", "Photos"],
           [[v.id, v.visit_date, v.rep.display_name, v.store.chain, v.store.store_number, v.store.city,
             local_dt(v.checked_in_at), local_dt(v.checked_out_at), v.distance_m, len(v.lines), v.notes,
             len(v.photos)] for v in visits], {11: 50})
    issues = db.scalars(select(Issue).order_by(Issue.id)).all()
    _sheet(wb, "Follow-ups", ["ID", "Chain", "Store #", "Program ID", "Discrepancy", "Description", "Action", "Owner",
                              "Due", "Status", "Raised By", "Raised", "Resolved", "Last Update"],
           [[i.id, i.store.chain, i.store.store_number, i.program.code if i.program else "", i.discrepancy_type,
             i.description, i.action, i.owner.display_name if i.owner else "", i.due_date, i.status,
             i.created_by.display_name, local_dt(i.created_at), local_dt(i.resolved_at),
             i.updates[-1].note if i.updates else ""] for i in issues], {6: 40, 7: 30, 14: 40})
    tasks = db.scalars(select(Task).order_by(Task.id)).all()
    _sheet(wb, "Tasks", ["ID", "Title", "Description", "Assignee", "Due", "Status", "Program ID", "Store",
                         "Completed", "Completion Note"],
           [[t.id, t.title, t.description, t.assignee.display_name, t.due_date, t.status,
             t.program.code if t.program else "", t.store.label if t.store else "", local_dt(t.completed_at),
             t.completion_note] for t in tasks])
    items = db.scalars(select(DataReviewItem).order_by(DataReviewItem.id)).all()
    _sheet(wb, "Data Review", ["#", "Account", "Brand", "Issue", "Action Needed", "Owner", "Resolved?"],
           [[d.id, d.account, d.brand, d.issue, d.action, d.owner, _yn(d.resolved)] for d in items], {4: 60, 5: 46})
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------- import ----------------
def _find_table(ws, first_header: str):
    rows = list(ws.iter_rows(values_only=True))
    for i, r in enumerate(rows[:15]):
        cells = [str(c).strip() if c is not None else "" for c in r]
        if first_header in cells:
            return cells, rows[i + 1:]
    return None, []


def _num(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def _date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            pass
    return None


def _txt(v):
    return "" if v is None else str(v).strip()


def import_plan(db: Session, raw: bytes, replace_promos: bool = True) -> dict:
    # data_only: the source workbook's formula cells are ignored; only typed inputs are read
    wb = load_workbook(io.BytesIO(raw), data_only=True)
    if "Chain Program" not in wb.sheetnames:
        raise ValueError("No 'Chain Program' sheet found.")
    head, rows = _find_table(wb["Chain Program"], "Program ID")
    if not head:
        raise ValueError("Couldn't find the 'Program ID' header on the Chain Program sheet.")
    idx = {h: i for i, h in enumerate(head)}
    stats = {"programs_added": 0, "programs_updated": 0, "promos_added": 0, "promos_replaced_for": 0, "skipped": 0}
    by_code = {p.code: p for p in db.scalars(select(Program)).all()}
    for r in rows:
        code = _txt(r[idx["Program ID"]]) if idx["Program ID"] < len(r) else ""
        if not code:
            continue
        get = lambda h: r[idx[h]] if h in idx and idx[h] < len(r) else None  # noqa: E731
        brand, account = _txt(get("Brand")), _txt(get("Account / Division"))
        if not brand or not account:
            stats["skipped"] += 1
            continue
        p = by_code.get(code)
        if p is None:
            p = Program(code=code)
            db.add(p)
            by_code[code] = p
            stats["programs_added"] += 1
        else:
            stats["programs_updated"] += 1
        for h, attr in PROGRAM_COLS[1:]:
            if h not in idx:
                continue
            v = get(h)
            if attr == "total_outlets":
                n = _num(v)
                v = int(n) if n is not None else None
            elif attr == "base_price":
                v = _num(v)
            elif attr == "last_verified":
                v = _date(v)
            else:
                v = _txt(v)
            setattr(p, attr, v)
        if "Active" in idx:
            p.active = _txt(get("Active")).upper() != "N"
        p.code = f"{p.brand} | {p.account}" if p.brand and p.account else code
    db.flush()
    by_code = {p.code: p for p in db.scalars(select(Program)).all()}

    if "Promo Calendar" in wb.sheetnames:
        head, rows = _find_table(wb["Promo Calendar"], "Program ID")
        if head:
            idx = {h: i for i, h in enumerate(head)}
            parsed = []
            for r in rows:
                get = lambda h: r[idx[h]] if h in idx and idx[h] < len(r) else None  # noqa: E731
                code = _txt(get("Program ID"))
                start, end = _date(get("Start")), _date(get("End"))
                offer = _txt(get("Offer"))
                if not code:
                    continue
                if code not in by_code or not start or not end or not offer:
                    stats["skipped"] += 1
                    continue
                parsed.append(Promo(program_id=by_code[code].id, sku=_txt(get("SKU / Pack")) or "All",
                                    offer_type=_txt(get("Offer Type")) or "TPR", offer=offer,
                                    unit_retail=_num(get("Unit Retail ($)")), case_cost=_num(get("Case Cost ($)")),
                                    start=start, end=end,
                                    display_required=_txt(get("Display Required")).upper() == "Y",
                                    source=_txt(get("Source"))))
            touched = {pr.program_id for pr in parsed}
            if replace_promos:
                for pid in touched:
                    for old in db.scalars(select(Promo).where(Promo.program_id == pid)).all():
                        db.delete(old)
                stats["promos_replaced_for"] = len(touched)
            db.add_all(parsed)
            stats["promos_added"] = len(parsed)
    db.flush()
    return stats
