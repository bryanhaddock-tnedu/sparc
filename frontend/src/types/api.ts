export interface DashboardSummary {
  fiscal_year: number;
  product_count: number;
  team_member_count: number;
  budget_amount: number;
  projected_spend: number;
  budget_remaining: number;
  budget_utilization_percent: number;
  forecasted_hours: number;
  forecasted_cost: number;
  fytd_hours: number;
  fytd_cost: number;
  remaining_hours: number;
  remaining_cost: number;
  variance_hours: number;
  variance_cost: number;
}

export interface AuthStatus {
  auth_enabled: boolean;
  authenticated: boolean;
  username: string | null;
}

export interface AdminDataExportOption {
  key: string;
  label: string;
  description: string;
  default_selected: boolean;
}

export interface AdminDataImportDatasetResult {
  key: string;
  label: string;
  created: number;
  updated: number;
  skipped: number;
  failed: number;
}

export interface AdminDataImportError {
  sheet: string;
  row: number;
  message: string;
}

export interface AdminDataImportResult {
  datasets: AdminDataImportDatasetResult[];
  errors: AdminDataImportError[];
  excluded_jira_refresh_data: string[];
}

export interface DashboardWorkTypeRow {
  bucket_id: number;
  bucket: string;
  bucket_code: string;
  forecast_hours: number;
  actual_hours: number;
  forecast_cost: number;
  actual_cost: number;
}

export type DashboardProductBucketTotal = DashboardWorkTypeRow;

export interface DashboardLaborMixRow {
  employment_type?: string;
  role?: string;
  forecast_hours: number;
  actual_hours: number;
  forecast_cost: number;
  actual_cost: number;
}

export interface DashboardLaborMix {
  hire_types: Array<{
    employment_type: string;
    forecast_hours: number;
    actual_hours: number;
    forecast_cost: number;
    actual_cost: number;
  }>;
  roles: Array<{
    role: string;
    forecast_hours: number;
    actual_hours: number;
    forecast_cost: number;
    actual_cost: number;
  }>;
}

export interface SystemScanResult {
  fiscal_year: number;
  generated_at: string;
  output: string;
}

export interface ProductSummaryRow {
  product_id: number;
  product: string;
  product_slug: string;
  jira_space_key: string | null;
  team_members: number;
  budget_amount: number;
  projected_spend: number;
  budget_remaining: number;
  budget_utilization_percent: number;
  forecasted_hours: number;
  forecasted_cost: number;
  fytd_hours: number;
  fytd_cost: number;
  remaining_hours: number;
  remaining_cost: number;
  variance_hours: number;
  variance_cost: number;
  bucket_totals: DashboardProductBucketTotal[];
  forecast_consumed_percent: number;
}

export interface Product {
  id: number;
  name: string;
  slug: string;
  jira_space_key: string | null;
  description: string | null;
  office: string | null;
  division: string | null;
  budget_amount: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductCreatePayload {
  name: string;
  jira_space_key?: string | null;
  description?: string | null;
  office?: string | null;
  division?: string | null;
  budget_amount?: number;
  is_active?: boolean;
}

export interface Bucket {
  id: number;
  code: string;
  name: string;
}

export interface ProductTeamMember {
  id: number;
  product_id: number;
  team_member_id: number;
  team_member: string;
  team_member_slug: string;
  role: string;
  team: string;
  bill_rate: number;
  employment_type: string;
  default_bucket_id: number | null;
  default_bucket: string | null;
  status: string;
  has_forecast_entries: boolean;
  has_actual_entries: boolean;
  created_at: string;
  updated_at: string;
}

export interface RoadmapItem {
  id: number;
  source: string;
  fiscal_year: number;
  product_id: number | null;
  product: string | null;
  product_slug: string | null;
  bucket_id: number | null;
  bucket: string | null;
  jira_issue_id: string;
  jira_issue_key: string;
  title: string;
  status: string | null;
  status_category: string | null;
  issue_type: string | null;
  program_area: string | null;
  source_url: string | null;
  linked_issue_count: number;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RoadmapItemMapPayload {
  product_id: number | null;
  bucket_id: number | null;
  program_area?: string | null;
}

export interface RoadmapTicketMapPayload {
  roadmap_item_id: number | null;
}

export interface RoadmapTicketMapResult {
  ticket_key: string;
  roadmap_item_id: number | null;
  roadmap_item_key: string | null;
  roadmap_item_title: string | null;
}

export interface RoadmapActualRow {
  roadmap_item_id: number | null;
  roadmap_item_key: string | null;
  roadmap_item_title: string | null;
  roadmap_item_status: string | null;
  program_area: string | null;
  product_id: number;
  product: string;
  product_slug: string;
  team_member_id: number;
  team_member: string;
  team_member_slug: string;
  bucket_id: number;
  bucket: string;
  bucket_code: string;
  fiscal_year: number;
  actual_hours: number;
  actual_cost: number;
  worklog_count: number;
  ticket_count: number;
  ticket_keys: string[];
  mapping_status: string;
}

export interface RoadmapSyncResult {
  source: string;
  sync_run: SyncRun;
  roadmap_items: number;
  linked_issues: number;
  removed_from_fiscal_year: number;
  fiscal_year_label: string | null;
}

export interface ProductTeamMemberPayload {
  team_member_id: number;
  default_bucket_id?: number | null;
  status?: string;
}

export interface ProductTeamMemberUpdatePayload {
  default_bucket_id?: number | null;
  status?: string;
}

export interface JiraProjectCatalog {
  id: number;
  jira_project_id: string;
  jira_project_key: string;
  jira_project_name: string;
  project_type_key: string | null;
  is_visible: boolean;
  is_archived: boolean;
  last_seen_at: string;
  last_checked_at: string;
}

export interface JiraProjectCatalogSyncResult {
  imported: number;
  projects: JiraProjectCatalog[];
}

export interface JiraProjectCatalogUpdatePayload {
  is_visible: boolean;
}

export interface JiraIntegrationStatus {
  configured: boolean;
  site_url: string | null;
  auth_email_configured: boolean;
  api_token_configured: boolean;
  missing: string[];
}

export interface ProductJiraSpace {
  id: number;
  product_id: number;
  jira_project_catalog_id: number | null;
  jira_project_id: string | null;
  jira_project_key: string;
  jira_project_name: string | null;
  is_active: boolean;
  scope_jql: string | null;
  validation_status: string;
  validation_message: string | null;
  last_validated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductJiraSpacePayload {
  jira_project_catalog_id?: number | null;
  jira_project_key?: string | null;
  is_active?: boolean;
  scope_jql?: string | null;
  replace_existing?: boolean;
}

export interface ProductJiraSpaceUpdatePayload {
  is_active?: boolean;
  scope_jql?: string | null;
}

export interface EstimationProfile {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  method_version: string;
  monthly_capacity_hours: number;
  actual_completeness_threshold: number;
  stale_ticket_window_days: number;
  forecast_future_months: boolean;
  future_month_average_window: number;
  excluded_statuses: string | null;
  low_activity_statuses: string | null;
  excluded_jira_project_keys: string | null;
  project_pause_dates: string | null;
  work_type_field_priority: string | null;
  story_point_weighting_enabled: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export type EstimationProfileUpdatePayload = Partial<
  Pick<
    EstimationProfile,
    | "name"
    | "description"
    | "is_active"
    | "method_version"
    | "monthly_capacity_hours"
    | "actual_completeness_threshold"
    | "stale_ticket_window_days"
    | "forecast_future_months"
    | "future_month_average_window"
    | "excluded_statuses"
    | "low_activity_statuses"
    | "excluded_jira_project_keys"
    | "project_pause_dates"
    | "work_type_field_priority"
    | "story_point_weighting_enabled"
    | "notes"
  >
>;

export interface EstimationRun {
  id: number;
  profile_id: number;
  method_version: string;
  fiscal_year: number;
  source_jira_updated_from: string | null;
  source_jira_updated_to: string | null;
  started_at: string;
  completed_at: string | null;
  status: string;
  imported_issue_count: number;
  estimated_entry_count: number;
  warning_count: number;
  error_summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface EstimationRunRequest {
  fiscal_year: number;
  profile_id?: number | null;
}

export interface EstimationPreview {
  fiscal_year: number;
  profile_id: number;
  method_version: string;
  imported_issue_count: number;
  included_issue_count: number;
  excluded_issue_count: number;
  unmapped_issue_count: number;
  estimated_entry_count: number;
  estimated_hours: number;
  warning_count: number;
  warnings: string[];
  run_id: number | null;
  status: string;
}

export interface ReportedValueRow {
  product_id: number;
  product: string;
  product_slug: string;
  team_member_id: number;
  team_member: string;
  team_member_slug: string;
  bucket_id: number;
  bucket: string;
  bucket_code: string;
  fiscal_month_id: number;
  month_label: string;
  month_sequence: number;
  calendar_year: number;
  calendar_month: number;
  forecast_hours: number;
  actual_hours: number;
  estimated_hours: number;
  reported_hours: number;
  reported_source: string;
  reported_reason: string;
  estimation_run_id: number | null;
}

export interface EstimatedIssueAllocation {
  id: number;
  estimation_run_id: number;
  team_member_id: number;
  team_member: string;
  team_member_slug: string;
  issue_id: string;
  issue_key: string;
  issue_summary: string | null;
  jira_project_key: string;
  product_id: number | null;
  product: string | null;
  bucket_id: number | null;
  bucket: string | null;
  fiscal_month_id: number | null;
  month_label: string | null;
  allocated_hours: number;
  issue_status: string | null;
  status_category: string | null;
  issue_type: string | null;
  story_points: number | null;
  issue_logged_hours: number;
  created_at_from_jira: string | null;
  updated_at_from_jira: string | null;
  resolved_at_from_jira: string | null;
  active_window_start: string | null;
  active_window_end: string | null;
  included: boolean;
  inclusion_reason: string | null;
  exclusion_reason: string | null;
}

export interface TeamMemberStoryPointMetric {
  estimation_run_id: number;
  team_member_id: number;
  story_points: number;
  issue_logged_hours: number;
  story_points_per_logged_hour: number | null;
  issue_count: number;
}

export interface DeliveryFlowIssue {
  estimation_run_id: number;
  team_member_id: number;
  team_member: string;
  team_member_slug: string;
  team: string;
  role: string;
  product_id: number | null;
  product: string | null;
  product_slug: string | null;
  bucket_id: number | null;
  bucket: string | null;
  issue_key: string;
  issue_summary: string | null;
  issue_status: string | null;
  status_category: string | null;
  delivery_stage: string;
  delivery_stage_label: string;
  story_points: number | null;
  issue_logged_hours: number;
  updated_days_ago: number | null;
}

export interface ProductSummary {
  product: Product;
  fiscal_year: number;
  budget_amount: number;
  projected_spend: number;
  budget_remaining: number;
  budget_utilization_percent: number;
  forecasted_hours: number;
  forecasted_cost: number;
  fytd_hours: number;
  fytd_cost: number;
  remaining_hours: number;
  remaining_cost: number;
  variance_hours: number;
  variance_cost: number;
}

export interface BucketDistributionRow {
  bucket_id: number;
  bucket: string;
  code: string;
  hours: number;
}

export interface FiscalMonth {
  id: number;
  fiscal_year: number;
  sequence: number;
  label: string;
  calendar_year: number;
  calendar_month: number;
}

export interface MonthCell {
  fiscal_month_id: number;
  sequence: number;
  label: string;
  forecast_hours: number;
  actual_hours: number;
  forecast_cost: number;
  actual_cost: number;
  remaining_hours: number;
  variance_hours: number;
  remaining_cost: number;
  variance_cost: number;
}

export interface BucketTableRow {
  team_member_id: number;
  team_member: string;
  team_member_slug: string;
  bill_rate: number;
  months: MonthCell[];
  totals: Omit<MonthCell, "fiscal_month_id" | "sequence" | "label">;
}

export interface BucketTable {
  bucket_id: number;
  code: string;
  name: string;
  rows: BucketTableRow[];
  totals: Omit<MonthCell, "fiscal_month_id" | "sequence" | "label">;
}

export interface ProductBucketTables {
  product: Product;
  fiscal_year: number;
  months: FiscalMonth[];
  buckets: BucketTable[];
}

export interface TeamMember {
  id: number;
  staff_id: string | null;
  name: string;
  slug: string;
  role: string;
  team: string;
  bill_rate: number;
  employment_type: string;
  contracting_company: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TeamMemberCreatePayload {
  staff_id?: string | null;
  name: string;
  role: string;
  team: string;
  bill_rate?: number;
  employment_type: string;
  contracting_company?: string | null;
  status?: string;
}

export interface TeamMemberProductRow {
  product_id: number;
  product: string;
  product_slug: string;
  bucket_id: number;
  bucket: string;
  forecast_hours: number;
  actual_hours: number;
  forecast_cost: number;
  actual_cost: number;
  remaining_cost: number;
}

export interface TeamMemberProducts {
  team_member: TeamMember;
  fiscal_year: number;
  months: FiscalMonth[];
  budget_amount: number;
  projected_spend: number;
  budget_remaining: number;
  budget_utilization_percent: number;
  products: TeamMemberProductRow[];
}

export interface TeamMemberActualWorklog {
  id: number;
  product_id: number;
  product: string;
  product_slug: string;
  bucket_id: number;
  bucket: string;
  fiscal_month_id: number;
  month_label: string;
  worked_on: string | null;
  hours: number;
  source: string;
  source_issue_id: string | null;
  source_ticket_key: string | null;
  source_worklog_id: string | null;
  source_project_key: string | null;
  sync_run_id: number | null;
  sync_completed_at: string | null;
}

export interface ForecastUpsertPayload {
  product_id: number;
  team_member_id: number;
  bucket_id?: number;
  bucket_code?: string;
  fiscal_month_id?: number;
  fiscal_year?: number;
  month_sequence?: number;
  hours: number;
}

export interface ForecastResponse {
  id: number;
  product_id: number;
  team_member_id: number;
  bucket_id: number;
  fiscal_month_id: number;
  hours: number;
}

export interface TeamImportRow {
  row: number;
  team_member_id: number | null;
  staff_id: string | null;
  name: string;
  action: string;
}

export interface TeamImportError {
  row: number;
  message: string;
}

export interface TeamImportResult {
  created: number;
  updated: number;
  skipped: number;
  failed: number;
  rows: TeamImportRow[];
  errors: TeamImportError[];
}

export interface UnmappedUser {
  id: number;
  jira_account_id: string;
  jira_display_name: string;
  jira_email: string | null;
  team_member_id: number | null;
  team_member: string | null;
}

export interface UnmappedProduct {
  id: number;
  jira_project_key: string;
  jira_project_name: string;
  product_id: number | null;
  product: string | null;
}

export type JiraUserMapping = UnmappedUser;
export type JiraProductMapping = UnmappedProduct;

export interface SyncRun {
  id: number;
  source: string;
  mode: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  imported_count: number;
  skipped_count: number;
  error_summary: string | null;
}

export interface JiraRovoSyncResult {
  source: string;
  sync_run: SyncRun;
  imported_worklogs: number;
  skipped_unmapped_worklogs: number;
  unmapped_users: UnmappedUser[];
  unmapped_products: UnmappedProduct[];
}
