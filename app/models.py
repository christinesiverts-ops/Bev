from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ROLES = ("manager", "rep", "viewer")
ISSUE_STATUSES = ("Open", "In Progress", "Resolved")
DATA_STATUSES = ("Current (2026)", "Confirm for 2026")
DISPLAY_CHOICES = ("Yes", "No", "N/A")
PRICE_CHECKS = ("Match", "Over plan", "Under plan", "No plan price")


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16), default="rep")
    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_manager(self) -> bool:
        return self.role == "manager"

    @property
    def can_log_visits(self) -> bool:
        return self.role in ("manager", "rep")


class Program(Base):
    """One brand x account plan row (the hot sheet)."""
    __tablename__ = "programs"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(160), unique=True, index=True)  # "Brand | Account"
    brand: Mapped[str] = mapped_column(String(40), index=True)
    chain: Mapped[str] = mapped_column(String(80), index=True)
    account: Mapped[str] = mapped_column(String(120))
    market: Mapped[str] = mapped_column(String(160), default="")
    outlets_text: Mapped[str] = mapped_column(String(255), default="")
    total_outlets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skus: Mapped[str] = mapped_column(Text, default="")
    case_rec: Mapped[str] = mapped_column(String(255), default="")
    shelf_callout: Mapped[str] = mapped_column(Text, default="")
    case_cost_text: Mapped[str] = mapped_column(String(255), default="")
    srp_text: Mapped[str] = mapped_column(String(255), default="")
    base_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    timing_text: Mapped[str] = mapped_column(String(255), default="")
    priority: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(120), default="")
    source: Mapped[str] = mapped_column(String(120), default="")
    data_status: Mapped[str] = mapped_column(String(32), default="Current (2026)")
    last_verified: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    promos: Mapped[list["Promo"]] = relationship(back_populates="program", cascade="all, delete-orphan",
                                                 order_by="Promo.start")


class Promo(Base):
    __tablename__ = "promos"
    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(80), default="All")
    offer_type: Mapped[str] = mapped_column(String(40), default="TPR")
    offer: Mapped[str] = mapped_column(String(255))
    unit_retail: Mapped[float | None] = mapped_column(Float, nullable=True)
    case_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    start: Mapped[date] = mapped_column(Date)
    end: Mapped[date] = mapped_column(Date)
    display_required: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(120), default="")

    program: Mapped[Program] = relationship(back_populates="promos")


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("chain", "store_number", name="uq_store_chain_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    chain: Mapped[str] = mapped_column(String(80), index=True)      # matches Program.chain
    division: Mapped[str] = mapped_column(String(120), default="")  # optional, e.g. "Seattle Div. #27"
    store_number: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(160), default="")
    address: Mapped[str] = mapped_column(String(255), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(20), default="")
    zip: Mapped[str] = mapped_column(String(20), default="")
    market_unit: Mapped[str] = mapped_column(String(80), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)   # False when a rep added it in the field
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    @property
    def label(self) -> str:
        bits = [self.chain, f"#{self.store_number}"]
        if self.city:
            bits.append(f"- {self.city}")
        return " ".join(bits)


class Visit(Base):
    __tablename__ = "visits"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    rep_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    visit_date: Mapped[date] = mapped_column(Date, index=True)
    checked_in_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checkin_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    checkin_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    checkin_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    store: Mapped[Store] = relationship()
    rep: Mapped[User] = relationship()
    lines: Mapped[list["AuditLine"]] = relationship(back_populates="visit", cascade="all, delete-orphan",
                                                    order_by="AuditLine.id")
    photos: Mapped[list["Photo"]] = relationship(back_populates="visit", cascade="all, delete-orphan")


class AuditLine(Base):
    """One program checked during a visit. Expected price is frozen at save time."""
    __tablename__ = "audit_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id", ondelete="CASCADE"), index=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), index=True)
    sku: Mapped[str] = mapped_column(String(80), default="All")
    expected_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_basis: Mapped[str] = mapped_column(String(255), default="")
    observed_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_check: Mapped[str] = mapped_column(String(20), default="")
    tag_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    planogram_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    in_stock_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    display: Mapped[str] = mapped_column(String(8), default="")
    discrepancy_type: Mapped[str] = mapped_column(String(80), default="None")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    visit: Mapped[Visit] = relationship(back_populates="lines")
    program: Mapped[Program] = relationship()
    photos: Mapped[list["Photo"]] = relationship(back_populates="line")


class Photo(Base):
    __tablename__ = "photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id", ondelete="CASCADE"), index=True)
    audit_line_id: Mapped[int | None] = mapped_column(ForeignKey("audit_lines.id", ondelete="SET NULL"), nullable=True)
    filename: Mapped[str] = mapped_column(String(80), unique=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    visit: Mapped[Visit] = relationship(back_populates="photos")
    line: Mapped[AuditLine | None] = relationship(back_populates="photos")


class Issue(Base):
    """A follow-up raised from a discrepancy (or by a manager)."""
    __tablename__ = "issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id"), nullable=True, index=True)
    audit_line_id: Mapped[int | None] = mapped_column(ForeignKey("audit_lines.id", ondelete="SET NULL"), nullable=True)
    discrepancy_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="Open", index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    store: Mapped[Store] = relationship()
    program: Mapped[Program | None] = relationship()
    owner: Mapped[User | None] = relationship(foreign_keys=[owner_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    updates: Mapped[list["IssueUpdate"]] = relationship(back_populates="issue", cascade="all, delete-orphan",
                                                        order_by="IssueUpdate.created_at")


class IssueUpdate(Base):
    __tablename__ = "issue_updates"
    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    issue: Mapped[Issue] = relationship(back_populates="updates")
    user: Mapped[User] = relationship()


class Task(Base):
    """Work a manager assigns: e.g. 'check WinCo Tier 2 displays by 10/13'."""
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id"), nullable=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="Open")   # Open / Done
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completion_note: Mapped[str] = mapped_column(Text, default="")

    program: Mapped[Program | None] = relationship()
    store: Mapped[Store | None] = relationship()
    assignee: Mapped[User] = relationship(foreign_keys=[assignee_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])


class DataReviewItem(Base):
    __tablename__ = "data_review"
    id: Mapped[int] = mapped_column(primary_key=True)
    account: Mapped[str] = mapped_column(String(160))
    brand: Mapped[str] = mapped_column(String(60))
    issue: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(120), default="")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    user: Mapped[User | None] = relationship()
