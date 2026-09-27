"""Visit and day recaps: one data model feeding the printable page and the PDF."""
import io
from dataclasses import dataclass, field
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import branding, config
from .common import local_dt
from .models import Issue, Route, User, Visit, WinCheck


@dataclass
class VisitRecap:
    v: Visit
    lines: list
    raised: list            # issues raised on this visit
    open_issues: list       # other open follow-ups at the store (next steps)
    wins: list
    placement_checks: list
    photos: list
    stats: dict = field(default_factory=dict)


def build_visit(db: Session, v: Visit) -> VisitRecap:
    line_ids = [l.id for l in v.lines]
    raised = db.scalars(select(Issue).where(Issue.audit_line_id.in_(line_ids))).all() if line_ids else []
    raised_ids = {i.id for i in raised}
    open_issues = [i for i in db.scalars(select(Issue).where(Issue.store_id == v.store_id, Issue.status != "Resolved")
                                         .order_by(Issue.due_date)).all() if i.id not in raised_ids]
    checks = db.scalars(select(WinCheck).where(WinCheck.visit_id == v.id)).all()
    priced = [l for l in v.lines if l.price_check in ("Match", "Over plan", "Under plan")]
    stats = {"checks": len(v.lines), "priced": len(priced),
             "match": sum(1 for l in priced if l.price_check == "Match"),
             "issues": sum(1 for l in v.lines if l.discrepancy_type != "None"),
             "wins": len(v.wins), "photos": len(v.photos)}
    return VisitRecap(v=v, lines=list(v.lines), raised=raised, open_issues=open_issues, wins=list(v.wins),
                      placement_checks=checks, photos=list(v.photos), stats=stats)


@dataclass
class DayRecap:
    rep: User
    day: date
    visits: list
    route: Route | None
    totals: dict


def build_day(db: Session, rep: User, day: date) -> DayRecap:
    visits = db.scalars(select(Visit).where(Visit.rep_id == rep.id, Visit.visit_date == day)
                        .order_by(Visit.checked_in_at)).all()
    recaps = [build_visit(db, v) for v in visits]
    route = db.scalar(select(Route).where(Route.assignee_id == rep.id, Route.route_date == day).order_by(Route.id.desc()))
    t = {k: sum(r.stats[k] for r in recaps) for k in ("checks", "priced", "match", "issues", "wins", "photos")}
    t["visits"] = len(recaps)
    if route:
        done = {v.store_id for v in visits}
        t["route_stops"] = len(route.stops)
        t["route_done"] = sum(1 for s in route.stops if s.store_id in done)
    return DayRecap(rep=rep, day=day, visits=recaps, route=route, totals=t)


# ---------------- PDF ----------------
def _styles(primary):
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#1C1917"))
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=10.5, textColor=colors.HexColor("#6B645C")),
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=20, leading=24),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=12, leading=16, spaceBefore=12,
                             spaceAfter=5, textColor=colors.HexColor(primary)),
        "eyebrow": ParagraphStyle("eyebrow", parent=base, fontName="Helvetica-Bold", fontSize=7.5, leading=10,
                                  textColor=colors.HexColor("#6B645C")),
        "right": ParagraphStyle("right", parent=base, alignment=TA_RIGHT),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.5, leading=11),
        "cellb": ParagraphStyle("cellb", parent=base, fontSize=8.5, leading=11, fontName="Helvetica-Bold"),
    }


def _esc(s) -> str:
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _money(v):
    return "—" if v is None else f"${v:,.2f}"


def _yn(b):
    return "—" if b is None else ("Yes" if b else "No")


RESULT_COLORS = {"Match": "#1F7A4D", "Over plan": "#B93A12", "Under plan": "#8A5A0A"}


def _logo_flowable():
    path = branding.upload_dir("company") / "logo.png"
    if path.is_file():
        img = Image(str(path))
        ratio = img.imageWidth / float(img.imageHeight or 1)
        img.drawHeight = 0.5 * inch
        img.drawWidth = min(1.6 * inch, 0.5 * inch * ratio)
        return img
    return None


def _header(story, st, title, subtitle, company):
    logo = _logo_flowable()
    left = [Paragraph(_esc(company).upper(), st["eyebrow"]), Paragraph(_esc(title), st["h1"]),
            Paragraph(_esc(subtitle), st["small"])]
    t = Table([[left, logo or ""]], colWidths=[5.4 * inch, 1.6 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [t, Spacer(1, 10)]


def _stat_row(st, items, primary):
    cells = [[Paragraph(f'<font size="16"><b>{_esc(v)}</b></font>', st["base"]) for _, v in items],
             [Paragraph(_esc(k).upper(), st["eyebrow"]) for k, _ in items]]
    t = Table(cells, colWidths=[7.0 * inch / len(items)] * len(items))
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F4EE")),
                           ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E7E1D8")),
                           ("LINEBEFORE", (1, 0), (-1, -1), 0.5, colors.HexColor("#E7E1D8")),
                           ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    return t


def _visit_story(story, st, r: VisitRecap, audience: str, primary: str, compact=False, include_photos=True):
    v = r.v
    if compact:
        story.append(Paragraph(f"{_esc(v.store.label)} <font size='8' color='#6B645C'>· in {local_dt(v.checked_in_at)}"
                               f"{' · out ' + local_dt(v.checked_out_at) if v.checked_out_at else ''}</font>", st["h2"]))
    # checks table
    if r.lines:
        rows = [[Paragraph(h, st["cellb"]) for h in ("Program", "SKU", "Plan", "Shelf", "Result", "Tag", "Location", "Stock", "Display")]]
        for l in r.lines:
            col = RESULT_COLORS.get(l.price_check, "#6B645C")
            rows.append([Paragraph(f"<b>{_esc(l.program.brand)}</b><br/>{_esc(l.program.account)}", st["cell"]),
                         Paragraph(_esc(l.sku), st["cell"]), Paragraph(_money(l.expected_price), st["cell"]),
                         Paragraph(_money(l.observed_price), st["cell"]),
                         Paragraph(f'<font color="{col}"><b>{_esc(l.price_check or "—")}</b></font>', st["cell"]),
                         Paragraph(_yn(l.tag_ok), st["cell"]), Paragraph(_yn(l.planogram_ok), st["cell"]),
                         Paragraph(_yn(l.in_stock_ok), st["cell"]), Paragraph(_esc(l.display or "—"), st["cell"])])
            extra = []
            if l.discrepancy_type != "None":
                extra.append(f'<font color="#B93A12"><b>{_esc(l.discrepancy_type)}</b></font>')
            if l.notes:
                extra.append(_esc(l.notes))
            if extra:
                rows.append([Paragraph(" · ".join(extra), st["small"])] + [""] * 8)
        t = Table(rows, colWidths=[w * inch for w in (1.55, .95, .6, .6, .8, .5, .7, .5, .6)], repeatRows=1)
        style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1EDE6")),
                 ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E7E1D8")),
                 ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
                 ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
        for i, row in enumerate(rows):
            if row[1] == "":
                style.append(("SPAN", (0, i), (-1, i)))
        t.setStyle(TableStyle(style))
        if not compact:
            story.append(Paragraph("Shelf checks", st["h2"]))
        story.append(t)
    elif not compact:
        story.append(Paragraph("No shelf checks logged.", st["small"]))

    if r.wins:
        story.append(Paragraph("Wins", st["h2"]))
        for w in r.wins:
            bits = [w.location, f"{w.cases} cases" if w.cases else "", f"{w.facings} facings/doors" if w.facings else ""]
            story.append(Paragraph(f"<b>{_esc(w.win_type)}</b> · {_esc(w.brand)}"
                                   f"{' · ' + _esc(', '.join(b for b in bits if b)) if any(bits) else ''}"
                                   f"{'<br/>' + _esc(w.notes) if w.notes else ''}", st["base"]))
            story.append(Spacer(1, 3))
    if r.placement_checks:
        story.append(Paragraph("Displays &amp; placements re-checked", st["h2"]))
        for c in r.placement_checks:
            state = "Still up" if c.status == "Active" else "Gone"
            story.append(Paragraph(f"{_esc(c.win.brand)} · {_esc(c.win.win_type)}: <b>{state}</b>", st["base"]))
    issues = list(r.raised) + ([] if compact else list(r.open_issues))
    if issues:
        story.append(Paragraph("Follow-ups &amp; next steps", st["h2"]))
        rows = [[Paragraph(h, st["cellb"]) for h in ("Issue", "Action", "Due", "Status")]]
        for i in issues:
            owner = f" ({_esc(i.owner.display_name)})" if (i.owner and audience == "team") else ""
            rows.append([Paragraph(f"<b>{_esc(i.discrepancy_type)}</b><br/>{_esc(i.description)}", st["cell"]),
                         Paragraph(_esc(i.action or "—") + owner, st["cell"]),
                         Paragraph(i.due_date.strftime("%m/%d/%Y") if i.due_date else "—", st["cell"]),
                         Paragraph(_esc(i.status), st["cell"])])
        t = Table(rows, colWidths=[2.9 * inch, 2.6 * inch, .8 * inch, .7 * inch], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1EDE6")),
                               ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E7E1D8")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)
    if v.notes and audience == "team":
        story.append(Paragraph("Visit notes", st["h2"]))
        story.append(Paragraph(_esc(v.notes).replace("\n", "<br/>"), st["base"]))
    if include_photos and r.photos:
        imgs = []
        for ph in r.photos[:8]:
            path = config.PHOTO_DIR / ph.filename
            if path.is_file():
                im = Image(str(path))
                ratio = im.imageHeight / float(im.imageWidth or 1)
                im.drawWidth = 1.65 * inch
                im.drawHeight = min(1.65 * inch * ratio, 2.2 * inch)
                imgs.append(im)
        if imgs:
            story.append(Paragraph("Photos", st["h2"]))
            grid = [imgs[i:i + 4] + [""] * (4 - len(imgs[i:i + 4])) for i in range(0, len(imgs), 4)]
            t = Table(grid, colWidths=[1.75 * inch] * 4)
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
            story.append(t)


def _footer(company):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#6B645C"))
        canvas.drawString(0.75 * inch, 0.5 * inch, company if company == "Chain Audit" else f"{company} · Chain Audit")
        canvas.drawRightString(7.75 * inch, 0.5 * inch, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def _doc(buf, title):
    return SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                             topMargin=0.7 * inch, bottomMargin=0.8 * inch, title=title, author="Chain Audit")


def visit_pdf(r: VisitRecap, audience: str = "team", include_photos: bool = True) -> bytes:
    site = branding.site()
    st = _styles(site["primary_color"])
    v = r.v
    buf = io.BytesIO()
    title = f"Visit recap · {v.store.chain} #{v.store.store_number}"
    story = []
    sub = f"{v.store.address} {v.store.city} {v.store.state} · {v.visit_date:%A, %B %d, %Y} · {v.rep.display_name}"
    if audience == "team":
        sub += f" · in {local_dt(v.checked_in_at)}" + (f", out {local_dt(v.checked_out_at)}" if v.checked_out_at else "")
    _header(story, st, title, sub, site["company_name"])
    s_ = r.stats
    story.append(_stat_row(st, [("Programs checked", s_["checks"]),
                                ("Price match", f"{s_['match']}/{s_['priced']}" if s_["priced"] else "—"),
                                ("Issues found", s_["issues"]), ("Wins", s_["wins"])], site["primary_color"]))
    _visit_story(story, st, r, audience, site["primary_color"], include_photos=include_photos)
    _doc(buf, title).build(story, onFirstPage=_footer(site["company_name"]), onLaterPages=_footer(site["company_name"]))
    return buf.getvalue()


def day_pdf(d: DayRecap) -> bytes:
    site = branding.site()
    st = _styles(site["primary_color"])
    buf = io.BytesIO()
    title = f"Day recap · {d.rep.display_name}"
    story = []
    _header(story, st, title, f"{d.day:%A, %B %d, %Y}", site["company_name"])
    t = d.totals
    items = [("Visits", t["visits"]), ("Checks", t["checks"]),
             ("Price match", f"{t['match']}/{t['priced']}" if t["priced"] else "—"), ("Issues", t["issues"]), ("Wins", t["wins"])]
    if "route_stops" in t:
        items.insert(1, ("Route", f"{t['route_done']}/{t['route_stops']}"))
    story.append(_stat_row(st, items, site["primary_color"]))
    if not d.visits:
        story.append(Spacer(1, 12))
        story.append(Paragraph("No visits logged on this day.", st["base"]))
    for r in d.visits:
        block = []
        _visit_story(block, st, r, "team", site["primary_color"], compact=True, include_photos=False)
        story.append(KeepTogether(block[:2]))
        story += block[2:]
    if d.route:
        done = {r.v.store_id for r in d.visits}
        missed = [s for s in d.route.stops if s.store_id not in done]
        if missed:
            story.append(Paragraph("Route stops not visited", st["h2"]))
            for s in missed:
                story.append(Paragraph(f"{_esc(s.store.label)}{' · ' + _esc(s.reason) if s.reason else ''}", st["base"]))
    _doc(buf, title).build(story, onFirstPage=_footer(site["company_name"]), onLaterPages=_footer(site["company_name"]))
    return buf.getvalue()
