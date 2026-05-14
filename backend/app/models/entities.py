from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    jira_space_key: Mapped[str | None] = mapped_column(String(40), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    forecasts: Mapped[list["ForecastEntry"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    actuals: Mapped[list["ActualEntry"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class TeamMember(TimestampMixin, Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[str | None] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    team: Mapped[str] = mapped_column(String(120), nullable=False)
    bill_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(80), default="Employee", nullable=False)
    contracting_company: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)

    forecasts: Mapped[list["ForecastEntry"]] = relationship(back_populates="team_member", cascade="all, delete-orphan")
    actuals: Mapped[list["ActualEntry"]] = relationship(back_populates="team_member", cascade="all, delete-orphan")


class Bucket(Base):
    __tablename__ = "buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    forecasts: Mapped[list["ForecastEntry"]] = relationship(back_populates="bucket")
    actuals: Mapped[list["ActualEntry"]] = relationship(back_populates="bucket")


class FiscalMonth(Base):
    __tablename__ = "fiscal_months"
    __table_args__ = (UniqueConstraint("fiscal_year", "sequence", name="uq_fiscal_month_year_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_year: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_month: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)

    forecasts: Mapped[list["ForecastEntry"]] = relationship(back_populates="fiscal_month")
    actuals: Mapped[list["ActualEntry"]] = relationship(back_populates="fiscal_month")


class ForecastEntry(TimestampMixin, Base):
    __tablename__ = "forecast_entries"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "team_member_id",
            "bucket_id",
            "fiscal_month_id",
            name="uq_forecast_product_member_bucket_month",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    team_member_id: Mapped[int] = mapped_column(ForeignKey("team_members.id"), nullable=False)
    bucket_id: Mapped[int] = mapped_column(ForeignKey("buckets.id"), nullable=False)
    fiscal_month_id: Mapped[int] = mapped_column(ForeignKey("fiscal_months.id"), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)

    product: Mapped[Product] = relationship(back_populates="forecasts")
    team_member: Mapped[TeamMember] = relationship(back_populates="forecasts")
    bucket: Mapped[Bucket] = relationship(back_populates="forecasts")
    fiscal_month: Mapped[FiscalMonth] = relationship(back_populates="forecasts")


class ActualEntry(TimestampMixin, Base):
    __tablename__ = "actual_entries"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "team_member_id",
            "bucket_id",
            "fiscal_month_id",
            "source_ticket_key",
            "source_worklog_id",
            name="uq_actual_source_worklog",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sync_run_id: Mapped[int | None] = mapped_column(ForeignKey("sync_runs.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    team_member_id: Mapped[int] = mapped_column(ForeignKey("team_members.id"), nullable=False)
    bucket_id: Mapped[int] = mapped_column(ForeignKey("buckets.id"), nullable=False)
    fiscal_month_id: Mapped[int] = mapped_column(ForeignKey("fiscal_months.id"), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="mock_jira_rovo", nullable=False)
    source_issue_id: Mapped[str | None] = mapped_column(String(120))
    source_ticket_key: Mapped[str | None] = mapped_column(String(80))
    source_worklog_id: Mapped[str | None] = mapped_column(String(120))
    source_account_id: Mapped[str | None] = mapped_column(String(160))
    source_project_key: Mapped[str | None] = mapped_column(String(80))
    source_payload_hash: Mapped[str | None] = mapped_column(String(128))
    is_team_member_time: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    worked_on: Mapped[date | None] = mapped_column(Date)

    sync_run: Mapped["SyncRun | None"] = relationship(back_populates="actual_entries")
    product: Mapped[Product] = relationship(back_populates="actuals")
    team_member: Mapped[TeamMember] = relationship(back_populates="actuals")
    bucket: Mapped[Bucket] = relationship(back_populates="actuals")
    fiscal_month: Mapped[FiscalMonth] = relationship(back_populates="actuals")


class JiraUserMapping(TimestampMixin, Base):
    __tablename__ = "jira_user_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jira_account_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    jira_display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    jira_email: Mapped[str | None] = mapped_column(String(160))
    team_member_id: Mapped[int | None] = mapped_column(ForeignKey("team_members.id"))

    team_member: Mapped[TeamMember | None] = relationship()


class JiraProductMapping(TimestampMixin, Base):
    __tablename__ = "jira_product_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jira_project_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    jira_project_name: Mapped[str] = mapped_column(String(160), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))

    product: Mapped[Product | None] = relationship()


class SyncRun(TimestampMixin, Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    mode: Mapped[str] = mapped_column(String(80), default="mock", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)

    actual_entries: Mapped[list[ActualEntry]] = relationship(back_populates="sync_run")
