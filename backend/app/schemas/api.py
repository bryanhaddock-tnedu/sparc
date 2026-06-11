from decimal import Decimal
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.product_org import (
    clean_product_org_value,
    product_division_error,
    product_office_error,
    product_org_pair_error,
)


class ApiMessage(BaseModel):
    message: str


class AdminDataExportOptionResponse(BaseModel):
    key: str
    label: str
    description: str
    default_selected: bool


class AdminDataImportDatasetResult(BaseModel):
    key: str
    label: str
    created: int
    updated: int
    skipped: int
    failed: int


class AdminDataImportError(BaseModel):
    sheet: str
    row: int
    message: str


class AdminDataImportResult(BaseModel):
    datasets: list[AdminDataImportDatasetResult]
    errors: list[AdminDataImportError]
    excluded_jira_refresh_data: list[str]


class ProductResponse(BaseModel):
    id: int
    name: str
    jira_space_key: str | None
    description: str | None
    office: str | None
    division: str | None
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
    office: str | None = None
    division: str | None = None
    budget_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    is_active: bool = True

    @field_validator("office", "division", mode="before")
    @classmethod
    def clean_org_value(cls, value: str | None) -> str | None:
        return clean_product_org_value(value)

    @model_validator(mode="after")
    def validate_product_org(self) -> "ProductCreate":
        if error := product_org_pair_error(self.office, self.division):
            raise ValueError(error)
        return self


class ProductUpdate(BaseModel):
    name: str | None = None
    jira_space_key: str | None = None
    description: str | None = None
    office: str | None = None
    division: str | None = None
    budget_amount: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("office", "division", mode="before")
    @classmethod
    def clean_org_value(cls, value: str | None) -> str | None:
        return clean_product_org_value(value)

    @field_validator("office")
    @classmethod
    def validate_office(cls, value: str | None) -> str | None:
        if error := product_office_error(value):
            raise ValueError(error)
        return value

    @field_validator("division")
    @classmethod
    def validate_division(cls, value: str | None) -> str | None:
        if error := product_division_error(value):
            raise ValueError(error)
        return value


class ProductTeamMemberCreate(BaseModel):
    team_member_id: int
    default_bucket_id: int | None = None
    status: str = "active"


class ProductTeamMemberUpdate(BaseModel):
    default_bucket_id: int | None = None
    status: str | None = None


class ProductTeamMemberResponse(BaseModel):
    id: int
    product_id: int
    team_member_id: int
    team_member: str
    role: str
    team: str
    bill_rate: float
    employment_type: str
    default_bucket_id: int | None
    default_bucket: str | None
    status: str
    has_forecast_entries: bool
    has_actual_entries: bool
    created_at: datetime
    updated_at: datetime


class JiraProjectCatalogResponse(BaseModel):
    id: int
    jira_project_id: str
    jira_project_key: str
    jira_project_name: str
    project_type_key: str | None
    is_visible: bool
    is_archived: bool
    last_seen_at: datetime
    last_checked_at: datetime


class JiraProjectCatalogSyncResponse(BaseModel):
    imported: int
    projects: list[JiraProjectCatalogResponse]


class JiraProjectCatalogUpdate(BaseModel):
    is_visible: bool


class JiraIntegrationStatusResponse(BaseModel):
    configured: bool
    site_url: str | None
    auth_email_configured: bool
    api_token_configured: bool
    missing: list[str]


class JiraLiveSyncRequest(BaseModel):
    fiscal_year: int = 2027


class ProductJiraSpaceCreate(BaseModel):
    jira_project_catalog_id: int | None = None
    jira_project_key: str | None = None
    is_active: bool = True
    scope_jql: str | None = None
    replace_existing: bool = False

    @model_validator(mode="after")
    def require_catalog_or_key(self) -> "ProductJiraSpaceCreate":
        if self.jira_project_catalog_id is None and not self.jira_project_key:
            raise ValueError("Either jira_project_catalog_id or jira_project_key is required")
        return self


class ProductJiraSpaceUpdate(BaseModel):
    is_active: bool | None = None
    scope_jql: str | None = None


class ProductJiraSpaceResponse(BaseModel):
    id: int
    product_id: int
    jira_project_catalog_id: int | None
    jira_project_id: str | None
    jira_project_key: str
    jira_project_name: str | None
    is_active: bool
    scope_jql: str | None
    validation_status: str
    validation_message: str | None
    last_validated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EstimationProfileResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    method_version: str
    monthly_capacity_hours: float
    actual_completeness_threshold: float
    stale_ticket_window_days: int
    forecast_future_months: bool
    future_month_average_window: int
    excluded_statuses: str | None
    low_activity_statuses: str | None
    excluded_jira_project_keys: str | None
    project_pause_dates: str | None
    work_type_field_priority: str | None
    story_point_weighting_enabled: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class EstimationProfileUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    method_version: str | None = None
    monthly_capacity_hours: Decimal | None = Field(default=None, ge=0)
    actual_completeness_threshold: Decimal | None = Field(default=None, ge=0, le=1)
    stale_ticket_window_days: int | None = Field(default=None, ge=1)
    forecast_future_months: bool | None = None
    future_month_average_window: int | None = Field(default=None, ge=1)
    excluded_statuses: str | None = None
    low_activity_statuses: str | None = None
    excluded_jira_project_keys: str | None = None
    project_pause_dates: str | None = None
    work_type_field_priority: str | None = None
    story_point_weighting_enabled: bool | None = None
    notes: str | None = None


class EstimationRunResponse(BaseModel):
    id: int
    profile_id: int
    method_version: str
    fiscal_year: int
    source_jira_updated_from: datetime | None
    source_jira_updated_to: datetime | None
    started_at: datetime
    completed_at: datetime | None
    status: str
    imported_issue_count: int
    estimated_entry_count: int
    warning_count: int
    error_summary: str | None
    created_at: datetime
    updated_at: datetime


class EstimationRunRequest(BaseModel):
    fiscal_year: int = 2027
    profile_id: int | None = None


class EstimationPreviewResponse(BaseModel):
    fiscal_year: int
    profile_id: int
    method_version: str
    imported_issue_count: int
    included_issue_count: int
    excluded_issue_count: int
    unmapped_issue_count: int
    estimated_entry_count: int
    estimated_hours: float
    warning_count: int
    warnings: list[str]
    run_id: int | None
    status: str


class EstimatedIssueAllocationResponse(BaseModel):
    id: int
    estimation_run_id: int
    team_member_id: int
    team_member: str
    issue_id: str
    issue_key: str
    issue_summary: str | None
    jira_project_key: str
    product_id: int | None
    product: str | None
    bucket_id: int | None
    bucket: str | None
    fiscal_month_id: int | None
    month_label: str | None
    allocated_hours: float
    issue_status: str | None
    status_category: str | None
    issue_type: str | None
    story_points: float | None
    issue_logged_hours: float
    created_at_from_jira: datetime | None
    updated_at_from_jira: datetime | None
    resolved_at_from_jira: datetime | None
    active_window_start: date | None
    active_window_end: date | None
    included: bool
    inclusion_reason: str | None
    exclusion_reason: str | None


class ReportedValueRowResponse(BaseModel):
    product_id: int
    product: str
    team_member_id: int
    team_member: str
    bucket_id: int
    bucket: str
    bucket_code: str
    fiscal_month_id: int
    month_label: str
    month_sequence: int
    calendar_year: int
    calendar_month: int
    forecast_hours: float
    actual_hours: float
    estimated_hours: float
    reported_hours: float
    reported_source: str
    reported_reason: str
    estimation_run_id: int | None


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


class DashboardWorkTypeRowResponse(BaseModel):
    bucket_id: int
    bucket: str
    bucket_code: str
    forecast_hours: float
    actual_hours: float
    forecast_cost: float
    actual_cost: float


class DashboardProductBucketTotalResponse(DashboardWorkTypeRowResponse):
    pass


class DashboardLaborMixHireTypeRowResponse(BaseModel):
    employment_type: str
    forecast_hours: float
    actual_hours: float
    forecast_cost: float
    actual_cost: float


class DashboardLaborMixRoleRowResponse(BaseModel):
    role: str
    forecast_hours: float
    actual_hours: float
    forecast_cost: float
    actual_cost: float


class DashboardLaborMixResponse(BaseModel):
    hire_types: list[DashboardLaborMixHireTypeRowResponse]
    roles: list[DashboardLaborMixRoleRowResponse]


class SystemScanResponse(BaseModel):
    fiscal_year: int
    generated_at: datetime
    output: str


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
    bucket_totals: list[DashboardProductBucketTotalResponse]
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
    months: list[FiscalMonthResponse]
    budget_amount: float
    projected_spend: float
    budget_remaining: float
    budget_utilization_percent: float
    products: list[TeamMemberProductRowResponse]


class TeamMemberActualWorklogResponse(BaseModel):
    id: int
    product_id: int
    product: str
    bucket_id: int
    bucket: str
    fiscal_month_id: int
    month_label: str
    worked_on: date | None
    hours: float
    source: str
    source_issue_id: str | None
    source_ticket_key: str | None
    source_worklog_id: str | None
    source_project_key: str | None
    sync_run_id: int | None
    sync_completed_at: datetime | None


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
