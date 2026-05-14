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

export interface ProductSummaryRow {
  product_id: number;
  product: string;
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
  forecast_consumed_percent: number;
}

export interface Product {
  id: number;
  name: string;
  jira_space_key: string | null;
  description: string | null;
  budget_amount: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
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
  role: string;
  team: string;
  bill_rate: number;
  employment_type: string;
  contracting_company: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TeamMemberProductRow {
  product_id: number;
  product: string;
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
  budget_amount: number;
  projected_spend: number;
  budget_remaining: number;
  budget_utilization_percent: number;
  products: TeamMemberProductRow[];
}

export interface ForecastUpsertPayload {
  product_id: number;
  team_member_id: number;
  bucket_id: number;
  fiscal_month_id: number;
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
