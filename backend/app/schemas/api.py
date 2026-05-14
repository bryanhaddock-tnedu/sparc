from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiMessage(BaseModel):
    message: str


class ProductResponse(BaseModel):
    id: int
    name: str
    jira_space_key: str | None
    description: str | None
    budget_amount: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TeamMemberResponse(BaseModel):
    id: int
    staff_id: str | None
    name: str
    role: str
    team: str
    bill_rate: float
    employment_type: str
    contracting_company: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProductCreate(BaseModel):
    name: str
    jira_space_key: str | None = None
    description: str | None = None
    budget_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = None
    jira_space_key: str | None = None
    description: str | None = None
    budget_amount: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class TeamMemberCreate(BaseModel):
    staff_id: str | None = None
    name: str
    role: str
    team: str
    bill_rate: Decimal = Field(default=Decimal("0.00"), ge=0)
    employment_type: str = "Employee"
    contracting_company: str | None = None
    status: str = "active"


class TeamMemberUpdate(BaseModel):
    staff_id: str | None = None
    name: str | None = None
    role: str | None = None
    team: str | None = None
    bill_rate: Decimal | None = Field(default=None, ge=0)
    employment_type: str | None = None
    contracting_company: str | None = None
    status: str | None = None


class ForecastUpsert(BaseModel):
    product_id: int
    team_member_id: int
    hours: Decimal = Field(ge=0)
    bucket_id: int | None = None
    bucket_code: str | None = None
    fiscal_month_id: int | None = None
    fiscal_year: int | None = None
    month_sequence: int | None = None

    model_config = ConfigDict(json_schema_extra={"examples": [{"product_id": 1, "team_member_id": 1, "bucket_code": "NET_NEW", "fiscal_year": 2026, "month_sequence": 1, "hours": 42}]})

    @model_validator(mode="after")
    def require_bucket_and_month(self) -> "ForecastUpsert":
        if self.bucket_id is None and self.bucket_code is None:
            raise ValueError("Either bucket_id or bucket_code is required")
        if self.fiscal_month_id is None and (self.fiscal_year is None or self.month_sequence is None):
            raise ValueError("Either fiscal_month_id or fiscal_year plus month_sequence is required")
        return self


class ForecastBatchUpsert(BaseModel):
    entries: list[ForecastUpsert] = Field(min_length=1)


class ForecastResponse(BaseModel):
    id: int
    product_id: int
    team_member_id: int
    bucket_id: int
    fiscal_month_id: int
    hours: float


class DashboardSummaryResponse(BaseModel):
    fiscal_year: int
    product_count: int
    team_member_count: int
    budget_amount: float
    projected_spend: float
    budget_remaining: float
    budget_utilization_percent: float
    forecasted_hours: float
    forecasted_cost: float
    fytd_hours: float
    fytd_cost: float
    remaining_hours: float
    remaining_cost: float
    variance_hours: float
    variance_cost: float


class ProductSummaryRowResponse(BaseModel):
    product_id: int
    product: str
    jira_space_key: str | None
    team_members: int
    budget_amount: float
    projected_spend: float
    budget_remaining: float
    budget_utilization_percent: float
    forecasted_hours: float
    forecasted_cost: float
    fytd_hours: float
    fytd_cost: float
    remaining_hours: float
    remaining_cost: float
    variance_hours: float
    variance_cost: float
    forecast_consumed_percent: float


class ProductSummaryResponse(BaseModel):
    product: ProductResponse
    fiscal_year: int
    budget_amount: float
    projected_spend: float
    budget_remaining: float
    budget_utilization_percent: float
    forecasted_hours: float
    forecasted_cost: float
    fytd_hours: float
    fytd_cost: float
    remaining_hours: float
    remaining_cost: float
    variance_hours: float
    variance_cost: float


class BucketDistributionResponse(BaseModel):
    bucket_id: int
    bucket: str
    code: str
    hours: float


class FiscalMonthResponse(BaseModel):
    id: int
    fiscal_year: int
    sequence: int
    label: str
    calendar_year: int
    calendar_month: int


class MonthCellResponse(BaseModel):
    fiscal_month_id: int
    sequence: int
    label: str
    forecast_hours: float
    actual_hours: float
    forecast_cost: float
    actual_cost: float
    remaining_hours: float
    variance_hours: float
    remaining_cost: float
    variance_cost: float


class TotalsResponse(BaseModel):
    forecast_hours: float
    actual_hours: float
    forecast_cost: float
    actual_cost: float
    remaining_hours: float
    variance_hours: float
    remaining_cost: float
    variance_cost: float


class BucketTableRowResponse(BaseModel):
    team_member_id: int
    team_member: str
    bill_rate: float
    months: list[MonthCellResponse]
    totals: TotalsResponse


class BucketTableResponse(BaseModel):
    bucket_id: int
    code: str
    name: str
    rows: list[BucketTableRowResponse]
    totals: TotalsResponse


class ProductBucketTablesResponse(BaseModel):
    product: ProductResponse
    fiscal_year: int
    months: list[FiscalMonthResponse]
    buckets: list[BucketTableResponse]


class TeamMemberProductRowResponse(BaseModel):
    product_id: int
    product: str
    bucket_id: int
    bucket: str
    forecast_hours: float
    actual_hours: float
    forecast_cost: float
    actual_cost: float
    remaining_cost: float


class TeamMemberProductsResponse(BaseModel):
    team_member: TeamMemberResponse
    fiscal_year: int
    budget_amount: float
    projected_spend: float
    budget_remaining: float
    budget_utilization_percent: float
    products: list[TeamMemberProductRowResponse]


class TeamImportError(BaseModel):
    row: int
    message: str


class TeamImportRow(BaseModel):
    row: int
    team_member_id: int | None = None
    staff_id: str | None = None
    name: str
    action: str


class TeamImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    failed: int
    rows: list[TeamImportRow]
    errors: list[TeamImportError]


class JiraUserMappingResponse(BaseModel):
    id: int
    jira_account_id: str
    jira_display_name: str
    jira_email: str | None
    team_member_id: int | None = None
    team_member: str | None = None


class JiraProductMappingResponse(BaseModel):
    id: int
    jira_project_key: str
    jira_project_name: str
    product_id: int | None = None
    product: str | None = None


class JiraUserMapRequest(BaseModel):
    team_member_id: int | None


class JiraProductMapRequest(BaseModel):
    product_id: int | None


class SyncRunResponse(BaseModel):
    id: int
    source: str
    mode: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    imported_count: int
    skipped_count: int
    error_summary: str | None


class JiraRovoSyncResponse(BaseModel):
    source: str
    sync_run: SyncRunResponse
    imported_worklogs: int
    skipped_unmapped_worklogs: int
    unmapped_users: list[JiraUserMappingResponse]
    unmapped_products: list[JiraProductMappingResponse]
