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
    slug: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    jira_space_key: Mapped[str | None] = mapped_column(String(40), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    office: Mapped[str | None] = mapped_column(String(80))
    division: Mapped[str | None] = mapped_column(String(160))
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    forecasts: Mapped[list["ForecastEntry"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    actuals: Mapped[list["ActualEntry"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    estimates: Mapped[list["EstimatedEntry"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    estimated_issue_allocations: Mapped[list["EstimatedIssueAllocation"]] = relationship(back_populates="product")
    team_members: Mapped[list["ProductTeamMember"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    jira_spaces: Mapped[list["ProductJiraSpace"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    budgets: Mapped[list["ProductBudget"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    roadmap_items: Mapped[list["RoadmapItem"]] = relationship(back_populates="product")


class ProductBudget(TimestampMixin, Base):
    __tablename__ = "product_budgets"
    __table_args__ = (UniqueConstraint("product_id", "fiscal_year", name="uq_product_budget_product_fiscal_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    product: Mapped[Product] = relationship(back_populates="budgets")


class TeamMember(TimestampMixin, Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[str | None] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    slug: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    team: Mapped[str] = mapped_column(String(120), nullable=False)
    bill_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(80), default="Employee", nullable=False)
    contracting_company: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)

    forecasts: Mapped[list["ForecastEntry"]] = relationship(back_populates="team_member", cascade="all, delete-orphan")
    actuals: Mapped[list["ActualEntry"]] = relationship(back_populates="team_member", cascade="all, delete-orphan")
    estimates: Mapped[list["EstimatedEntry"]] = relationship(back_populates="team_member", cascade="all, delete-orphan")
    estimated_issue_allocations: Mapped[list["EstimatedIssueAllocation"]] = relationship(back_populates="team_member")
    product_assignments: Mapped[list["ProductTeamMember"]] = relationship(back_populates="team_member", cascade="all, delete-orphan")


class Bucket(Base):
    __tablename__ = "buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    forecasts: Mapped[list["ForecastEntry"]] = relationship(back_populates="bucket")
    actuals: Mapped[list["ActualEntry"]] = relationship(back_populates="bucket")
    estimates: Mapped[list["EstimatedEntry"]] = relationship(back_populates="bucket")
    estimated_issue_allocations: Mapped[list["EstimatedIssueAllocation"]] = relationship(back_populates="bucket")
    product_team_members: Mapped[list["ProductTeamMember"]] = relationship(back_populates="default_bucket")
    roadmap_items: Mapped[list["RoadmapItem"]] = relationship(back_populates="bucket")


class ProductTeamMember(TimestampMixin, Base):
    __tablename__ = "product_team_members"
    __table_args__ = (UniqueConstraint("product_id", "team_member_id", name="uq_product_team_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    team_member_id: Mapped[int] = mapped_column(ForeignKey("team_members.id"), nullable=False)
    default_bucket_id: Mapped[int | None] = mapped_column(ForeignKey("buckets.id"))
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)

    product: Mapped[Product] = relationship(back_populates="team_members")
    team_member: Mapped[TeamMember] = relationship(back_populates="product_assignments")
    default_bucket: Mapped[Bucket | None] = relationship(back_populates="product_team_members")


class JiraProjectCatalog(TimestampMixin, Base):
    __tablename__ = "jira_project_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jira_project_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    jira_project_key: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    jira_project_name: Mapped[str] = mapped_column(String(160), nullable=False)
    project_type_key: Mapped[str | None] = mapped_column(String(80))
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    product_spaces: Mapped[list["ProductJiraSpace"]] = relationship(back_populates="catalog_entry")


class ProductJiraSpace(TimestampMixin, Base):
    __tablename__ = "product_jira_spaces"
    __table_args__ = (
        UniqueConstraint("product_id", "jira_project_key", name="uq_product_jira_space_product_key"),
        UniqueConstraint("jira_project_key", name="uq_product_jira_space_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    jira_project_catalog_id: Mapped[int | None] = mapped_column(ForeignKey("jira_project_catalog.id"))
    jira_project_id: Mapped[str | None] = mapped_column(String(80))
    jira_project_key: Mapped[str] = mapped_column(String(80), nullable=False)
    jira_project_name: Mapped[str | None] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scope_jql: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    validation_message: Mapped[str | None] = mapped_column(Text)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(back_populates="jira_spaces")
    catalog_entry: Mapped[JiraProjectCatalog | None] = relationship(back_populates="product_spaces")


class RoadmapItem(TimestampMixin, Base):
    __tablename__ = "roadmap_items"
    __table_args__ = (
        UniqueConstraint("source", "jira_issue_id", name="uq_roadmap_item_source_issue_id"),
        UniqueConstraint("source", "jira_issue_key", name="uq_roadmap_item_source_issue_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), default="jira_product_discovery", nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, default=2027, index=True, nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    bucket_id: Mapped[int | None] = mapped_column(ForeignKey("buckets.id"))
    jira_issue_id: Mapped[str] = mapped_column(String(120), nullable=False)
    jira_issue_key: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(String(120))
    status_category: Mapped[str | None] = mapped_column(String(80))
    issue_type: Mapped[str | None] = mapped_column(String(120))
    program_area: Mapped[str | None] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_payload_hash: Mapped[str | None] = mapped_column(String(128))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product | None] = relationship(back_populates="roadmap_items")
    bucket: Mapped[Bucket | None] = relationship(back_populates="roadmap_items")
    issue_links: Mapped[list["RoadmapItemIssueLink"]] = relationship(back_populates="roadmap_item", cascade="all, delete-orphan")


class RoadmapItemIssueLink(TimestampMixin, Base):
    __tablename__ = "roadmap_item_issue_links"
    __table_args__ = (UniqueConstraint("roadmap_item_id", "jira_issue_key", name="uq_roadmap_item_issue_link"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roadmap_item_id: Mapped[int] = mapped_column(ForeignKey("roadmap_items.id"), nullable=False)
    jira_issue_id: Mapped[str | None] = mapped_column(String(120))
    jira_issue_key: Mapped[str] = mapped_column(String(80), nullable=False)
    jira_issue_summary: Mapped[str | None] = mapped_column(Text)
    jira_project_key: Mapped[str | None] = mapped_column(String(80))
    relationship_type: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(80), default="jira_issue_link", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    roadmap_item: Mapped[RoadmapItem] = relationship(back_populates="issue_links")


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
    estimates: Mapped[list["EstimatedEntry"]] = relationship(back_populates="fiscal_month")
    estimated_issue_allocations: Mapped[list["EstimatedIssueAllocation"]] = relationship(back_populates="fiscal_month")


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


class EstimationProfile(TimestampMixin, Base):
    __tablename__ = "estimation_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    method_version: Mapped[str] = mapped_column(String(80), nullable=False)
    monthly_capacity_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("120.00"), nullable=False)
    actual_completeness_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.7500"), nullable=False)
    stale_ticket_window_days: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    forecast_future_months: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    future_month_average_window: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    excluded_statuses: Mapped[str | None] = mapped_column(Text)
    low_activity_statuses: Mapped[str | None] = mapped_column(Text)
    excluded_jira_project_keys: Mapped[str | None] = mapped_column(Text)
    project_pause_dates: Mapped[str | None] = mapped_column(Text)
    work_type_field_priority: Mapped[str | None] = mapped_column(Text)
    story_point_weighting_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    estimation_runs: Mapped[list["EstimationRun"]] = relationship(back_populates="profile")


class EstimationRun(TimestampMixin, Base):
    __tablename__ = "estimation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("estimation_profiles.id"), nullable=False)
    method_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rules_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    source_jira_updated_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_jira_updated_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), default="running", nullable=False)
    imported_issue_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_entry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[EstimationProfile] = relationship(back_populates="estimation_runs")
    estimated_entries: Mapped[list["EstimatedEntry"]] = relationship(back_populates="estimation_run", cascade="all, delete-orphan")
    issue_allocations: Mapped[list["EstimatedIssueAllocation"]] = relationship(back_populates="estimation_run", cascade="all, delete-orphan")


class EstimatedEntry(TimestampMixin, Base):
    __tablename__ = "estimated_entries"
    __table_args__ = (
        UniqueConstraint(
            "estimation_run_id",
            "product_id",
            "team_member_id",
            "bucket_id",
            "fiscal_month_id",
            name="uq_estimate_run_product_member_bucket_month",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estimation_run_id: Mapped[int] = mapped_column(ForeignKey("estimation_runs.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    team_member_id: Mapped[int] = mapped_column(ForeignKey("team_members.id"), nullable=False)
    bucket_id: Mapped[int] = mapped_column(ForeignKey("buckets.id"), nullable=False)
    fiscal_month_id: Mapped[int] = mapped_column(ForeignKey("fiscal_months.id"), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    method_version: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text)

    estimation_run: Mapped[EstimationRun] = relationship(back_populates="estimated_entries")
    product: Mapped[Product] = relationship(back_populates="estimates")
    team_member: Mapped[TeamMember] = relationship(back_populates="estimates")
    bucket: Mapped[Bucket] = relationship(back_populates="estimates")
    fiscal_month: Mapped[FiscalMonth] = relationship(back_populates="estimates")


class EstimatedIssueAllocation(TimestampMixin, Base):
    __tablename__ = "estimated_issue_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estimation_run_id: Mapped[int] = mapped_column(ForeignKey("estimation_runs.id"), nullable=False)
    team_member_id: Mapped[int] = mapped_column(ForeignKey("team_members.id"), nullable=False)
    issue_id: Mapped[str] = mapped_column(String(120), nullable=False)
    issue_key: Mapped[str] = mapped_column(String(80), nullable=False)
    issue_summary: Mapped[str | None] = mapped_column(Text)
    jira_project_key: Mapped[str] = mapped_column(String(80), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    bucket_id: Mapped[int | None] = mapped_column(ForeignKey("buckets.id"))
    fiscal_month_id: Mapped[int | None] = mapped_column(ForeignKey("fiscal_months.id"))
    allocated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    issue_status: Mapped[str | None] = mapped_column(String(120))
    status_category: Mapped[str | None] = mapped_column(String(80))
    issue_type: Mapped[str | None] = mapped_column(String(120))
    story_points: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    issue_logged_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    created_at_from_jira: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at_from_jira: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at_from_jira: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_window_start: Mapped[date | None] = mapped_column(Date)
    active_window_end: Mapped[date | None] = mapped_column(Date)
    included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    inclusion_reason: Mapped[str | None] = mapped_column(Text)
    exclusion_reason: Mapped[str | None] = mapped_column(Text)

    estimation_run: Mapped[EstimationRun] = relationship(back_populates="issue_allocations")
    team_member: Mapped[TeamMember] = relationship(back_populates="estimated_issue_allocations")
    product: Mapped[Product | None] = relationship(back_populates="estimated_issue_allocations")
    bucket: Mapped[Bucket | None] = relationship(back_populates="estimated_issue_allocations")
    fiscal_month: Mapped[FiscalMonth | None] = relationship(back_populates="estimated_issue_allocations")
