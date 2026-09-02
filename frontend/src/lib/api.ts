import type {
  AdminDataExportOption,
  AdminDataImportResult,
  AttributionChange,
  AppUser,
  AppUserCreatePayload,
  AppUserUpdatePayload,
  AuthStatus,
  Bucket,
  BucketDistributionRow,
  DashboardLaborMix,
  DashboardSummary,
  DashboardWorkTypeRow,
  DeliveryFlowIssue,
  EstimatedIssueAllocation,
  EstimationPreview,
  EstimationProfile,
  EstimationProfileUpdatePayload,
  JiraTeamEstimationProfile,
  JiraTeamEstimationProfilePayload,
  EstimationRun,
  EstimationRunRequest,
  ForecastRecommendationDecision,
  ForecastRecommendationDecisionPayload,
  ForecastResponse,
  ForecastUpsertPayload,
  JiraIntegrationStatus,
  JiraProductMapping,
  JiraProjectCatalog,
  JiraProjectCatalogSyncResult,
  JiraProjectCatalogUpdatePayload,
  JiraRovoSyncResult,
  LaborCostReport,
  LaborCostReportDimension,
  LaborCostReportMetric,
  LaborCostReportOptionalDimension,
  LaborCostReportSort,
  JiraUserMapping,
  JiraWorklogExclusionSummary,
  Product,
  ProductBucketTables,
  ProductCreatePayload,
  ProductJiraSpace,
  ProductJiraSpaceMoveResult,
  ProductJiraSpacePayload,
  ProductJiraSpaceUpdatePayload,
  ProductPeople,
  ProductRoleBreakdownRow,
  TicketCostReceipt,
  ProductSummary,
  ProductSummaryRow,
  ProductTeamMember,
  ProductTeamMemberPayload,
  ProductTeamMemberUpdatePayload,
  ReportedValueRow,
  RoadmapActualRow,
  RoadmapForecastAllocationUpsertPayload,
  RoadmapItem,
  RoadmapItemMapPayload,
  RoadmapSyncResult,
  RoadmapTicketMapPayload,
  RoadmapTicketMapResult,
  SyncRun,
  SystemScanResult,
  TeamImportResult,
  TeamMember,
  TeamMemberActualWorklog,
  TeamMemberCreatePayload,
  TeamMemberProducts,
  TeamRoadmapForecastPlan,
  TeamMemberStoryPointMetric,
  UnmappedProduct,
  UnmappedUser,
} from "../types/api";

type ProductRef = number | string;
type TeamMemberRef = number | string;
import { appConfig } from "./config";

const API_BASE_URL = appConfig.apiBaseUrl;
const DEFAULT_FISCAL_YEAR = appConfig.fiscalYear;

type DashboardScopeParams = {
  monthSequence?: number | null;
};

type RoadmapActualParams = {
  monthSequence?: number | null;
};

type LaborCostReportParams = {
  lead: LaborCostReportDimension;
  second?: LaborCostReportOptionalDimension;
  third?: LaborCostReportOptionalDimension;
  fourth?: LaborCostReportOptionalDimension;
  sort?: LaborCostReportSort;
};

function dashboardQuery(fiscalYear: number, params: DashboardScopeParams = {}) {
  const search = new URLSearchParams({ fiscal_year: String(fiscalYear) });
  if (params.monthSequence != null) search.set("month_sequence", String(params.monthSequence));
  return search.toString();
}

function roadmapActualQuery(fiscalYear: number, params: RoadmapActualParams = {}) {
  const search = new URLSearchParams({ fiscal_year: String(fiscalYear) });
  if (params.monthSequence != null) search.set("month_sequence", String(params.monthSequence));
  return search.toString();
}

function laborCostReportQuery(fiscalYear: number, params: LaborCostReportParams) {
  const search = new URLSearchParams({
    fiscal_year: String(fiscalYear),
    lead: params.lead,
    second: params.second ?? "none",
    third: params.third ?? "none",
    fourth: params.fourth ?? "none",
    sort: params.sort ?? "forecast_cost",
  });
  return search.toString();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    const message = await responseErrorMessage(response);
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function upload<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const message = await responseErrorMessage(response);
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function download(path: string, fallbackFilename = "sparc-download"): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE_URL}${path}`, { credentials: "include" });
  if (!response.ok) {
    const message = await responseErrorMessage(response);
    throw new Error(message || `Request failed with ${response.status}`);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  const filename = match?.[1] ?? fallbackFilename;
  return { blob: await response.blob(), filename };
}

async function responseErrorMessage(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) return "";
  try {
    const payload = JSON.parse(text) as { detail?: { message?: string } | string };
    if (typeof payload.detail === "string") return payload.detail;
    return payload.detail?.message ?? text;
  } catch {
    return text;
  }
}

export const api = {
  fiscalYear: DEFAULT_FISCAL_YEAR,
  authStatus: () => request<AuthStatus>("/api/auth/status"),
  login: (username: string, password: string) =>
    request<AuthStatus>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () =>
    request<AuthStatus>("/api/auth/logout", {
      method: "POST",
    }),
  adminDataExportOptions: () => request<AdminDataExportOption[]>("/api/admin-data/export-options"),
  adminUsers: () => request<AppUser[]>("/api/admin/users"),
  createAdminUser: (payload: AppUserCreatePayload) =>
    request<AppUser>("/api/admin/users", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAdminUser: (userId: number, payload: AppUserUpdatePayload) =>
    request<AppUser>(`/api/admin/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  exportAdminData: (datasets: string[]) => {
    const params = new URLSearchParams();
    datasets.forEach((dataset) => params.append("datasets", dataset));
    return download(`/api/admin-data/export${params.toString() ? `?${params.toString()}` : ""}`, "sparc-admin-data.zip");
  },
  importAdminData: (file: File, datasets: string[]) => {
    const params = new URLSearchParams();
    datasets.forEach((dataset) => params.append("datasets", dataset));
    const formData = new FormData();
    formData.append("file", file);
    return upload<AdminDataImportResult>(`/api/admin-data/import${params.toString() ? `?${params.toString()}` : ""}`, formData);
  },
  dashboardSummary: (fiscalYear = DEFAULT_FISCAL_YEAR) => request<DashboardSummary>(`/api/dashboard/summary?fiscal_year=${fiscalYear}`),
  dashboardProducts: (fiscalYear = DEFAULT_FISCAL_YEAR, params: DashboardScopeParams = {}) =>
    request<ProductSummaryRow[]>(`/api/dashboard/products?${dashboardQuery(fiscalYear, params)}`),
  dashboardWorkTypes: (fiscalYear = DEFAULT_FISCAL_YEAR, params: DashboardScopeParams = {}) =>
    request<DashboardWorkTypeRow[]>(`/api/dashboard/work-types?${dashboardQuery(fiscalYear, params)}`),
  dashboardLaborMix: (fiscalYear = DEFAULT_FISCAL_YEAR, params: DashboardScopeParams = {}) =>
    request<DashboardLaborMix>(`/api/dashboard/labor-mix?${dashboardQuery(fiscalYear, params)}`),
  systemScan: (
    fiscalYear = DEFAULT_FISCAL_YEAR,
    params: { budgetWarningPercent?: number; memberForecastLimitHours?: number; workingDays?: number } = {},
  ) => {
    const search = new URLSearchParams({
      fiscal_year: String(fiscalYear),
      budget_warning_percent: String(params.budgetWarningPercent ?? 85),
      member_forecast_limit_hours: String(params.memberForecastLimitHours ?? 10),
      working_days: String(params.workingDays ?? 7),
    });
    return request<SystemScanResult>(`/api/system-scan?${search.toString()}`);
  },
  productSummary: (productRef: ProductRef, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<ProductSummary>(`/api/products/${encodeURIComponent(String(productRef))}/summary?fiscal_year=${fiscalYear}`),
  productRoleBreakdown: (productRef: ProductRef, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<ProductRoleBreakdownRow[]>(`/api/products/${encodeURIComponent(String(productRef))}/role-breakdown?fiscal_year=${fiscalYear}`),
  productTicketCostReceipts: (productRef: ProductRef, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<TicketCostReceipt[]>(`/api/products/${encodeURIComponent(String(productRef))}/ticket-cost-receipts?fiscal_year=${fiscalYear}`),
  bucketDistribution: (productRef: ProductRef, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<BucketDistributionRow[]>(`/api/products/${encodeURIComponent(String(productRef))}/bucket-distribution?fiscal_year=${fiscalYear}`),
  productBucketTables: (productRef: ProductRef, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<ProductBucketTables>(`/api/products/${encodeURIComponent(String(productRef))}/bucket-tables?fiscal_year=${fiscalYear}`),
  productRoadmapActuals: (productRef: ProductRef, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<RoadmapActualRow[]>(`/api/products/${encodeURIComponent(String(productRef))}/roadmap-actuals?fiscal_year=${fiscalYear}`),
  productRoadmapItems: (productRef: ProductRef, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<RoadmapItem[]>(`/api/products/${encodeURIComponent(String(productRef))}/roadmap-items?fiscal_year=${fiscalYear}`),
  products: (fiscalYear = DEFAULT_FISCAL_YEAR) => request<Product[]>(`/api/products?fiscal_year=${fiscalYear}`),
  buckets: () => request<Bucket[]>("/api/products/buckets"),
  createProduct: (payload: ProductCreatePayload, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<Product>(`/api/products?fiscal_year=${fiscalYear}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProduct: (
    productId: ProductRef,
    payload: Partial<Pick<Product, "name" | "jira_space_key" | "description" | "office" | "division" | "budget_amount" | "is_active">>,
    fiscalYear = DEFAULT_FISCAL_YEAR,
  ) =>
    request<Product>(`/api/products/${encodeURIComponent(String(productId))}?fiscal_year=${fiscalYear}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteProduct: (productId: ProductRef) =>
    request<{ message: string }>(`/api/products/${encodeURIComponent(String(productId))}`, {
      method: "DELETE",
    }),
  productTeamMembers: (productId: ProductRef) => request<ProductTeamMember[]>(`/api/products/${encodeURIComponent(String(productId))}/team-members`),
  productPeople: (productId: ProductRef) => request<ProductPeople>(`/api/products/${encodeURIComponent(String(productId))}/people`),
  addProductTeamMember: (productId: ProductRef, payload: ProductTeamMemberPayload) =>
    request<ProductTeamMember>(`/api/products/${encodeURIComponent(String(productId))}/team-members`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProductTeamMember: (productId: ProductRef, assignmentId: number, payload: ProductTeamMemberUpdatePayload) =>
    request<ProductTeamMember>(`/api/products/${encodeURIComponent(String(productId))}/team-members/${assignmentId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  removeProductTeamMember: (productId: ProductRef, assignmentId: number) =>
    request<{ message: string }>(`/api/products/${encodeURIComponent(String(productId))}/team-members/${assignmentId}`, {
      method: "DELETE",
    }),
  productJiraSpaces: (productId: ProductRef) => request<ProductJiraSpace[]>(`/api/products/${encodeURIComponent(String(productId))}/jira-spaces`),
  addProductJiraSpace: (productId: ProductRef, payload: ProductJiraSpacePayload) =>
    request<ProductJiraSpace>(`/api/products/${encodeURIComponent(String(productId))}/jira-spaces`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProductJiraSpace: (productId: ProductRef, spaceId: number, payload: ProductJiraSpaceUpdatePayload) =>
    request<ProductJiraSpace>(`/api/products/${encodeURIComponent(String(productId))}/jira-spaces/${spaceId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  moveProductJiraSpace: (productId: ProductRef, spaceId: number, targetProductId: number, reason?: string) =>
    request<ProductJiraSpaceMoveResult>(`/api/products/${encodeURIComponent(String(productId))}/jira-spaces/${spaceId}/move`, {
      method: "POST",
      body: JSON.stringify({ target_product_id: targetProductId, reason }),
    }),
  removeProductJiraSpace: (productId: ProductRef, spaceId: number) =>
    request<{ message: string }>(`/api/products/${encodeURIComponent(String(productId))}/jira-spaces/${spaceId}`, {
      method: "DELETE",
    }),
  validateProductJiraSpace: (productId: ProductRef, spaceId: number) =>
    request<ProductJiraSpace>(`/api/products/${encodeURIComponent(String(productId))}/jira-spaces/${spaceId}/validate`, {
      method: "POST",
    }),
  teamMembers: () => request<TeamMember[]>("/api/team-members"),
  createTeamMember: (payload: TeamMemberCreatePayload) =>
    request<TeamMember>("/api/team-members", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTeamMember: (teamMemberId: TeamMemberRef, payload: Partial<TeamMember>) =>
    request<TeamMember>(`/api/team-members/${encodeURIComponent(String(teamMemberId))}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  teamMemberProducts: (teamMemberId: TeamMemberRef, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<TeamMemberProducts>(`/api/team-members/${encodeURIComponent(String(teamMemberId))}/products?fiscal_year=${fiscalYear}`),
  teamMemberActualWorklogs: (teamMemberId: TeamMemberRef, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<TeamMemberActualWorklog[]>(`/api/team-members/${encodeURIComponent(String(teamMemberId))}/actual-worklogs?fiscal_year=${fiscalYear}`),
  teamMemberRoadmapActuals: (teamMemberId: TeamMemberRef, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<RoadmapActualRow[]>(`/api/team-members/${encodeURIComponent(String(teamMemberId))}/roadmap-actuals?fiscal_year=${fiscalYear}`),
  teamRoadmapForecastPlan: (teamRef: string, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<TeamRoadmapForecastPlan>(`/api/teams/${encodeURIComponent(teamRef)}/roadmap-forecast-plan?fiscal_year=${fiscalYear}`),
  upsertTeamRoadmapForecastPlan: (teamRef: string, fiscalYear = DEFAULT_FISCAL_YEAR, entries: RoadmapForecastAllocationUpsertPayload[]) =>
    request<TeamRoadmapForecastPlan>(`/api/teams/${encodeURIComponent(teamRef)}/roadmap-forecast-plan?fiscal_year=${fiscalYear}`, {
      method: "PUT",
      body: JSON.stringify({ entries }),
    }),
  upsertForecast: (payload: ForecastUpsertPayload) =>
    request<ForecastResponse>("/api/forecasts", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  upsertForecastBatch: (entries: ForecastUpsertPayload[]) =>
    request<ForecastResponse[]>("/api/forecasts/batch", {
      method: "PUT",
      body: JSON.stringify({ entries }),
    }),
  removeForecastLine: (payload: { product_id: number; team_member_id: number; bucket_id: number; fiscal_year: number }) => {
    const params = new URLSearchParams(Object.entries(payload).map(([key, value]) => [key, String(value)]));
    return request<{ message: string }>(`/api/forecasts/line?${params.toString()}`, { method: "DELETE" });
  },
  importTeamMembers: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return upload<TeamImportResult>("/api/team-members/import", formData);
  },
  syncMockJiraRovo: () =>
    request<JiraRovoSyncResult>("/api/integrations/jira-rovo/sync", {
      method: "POST",
    }),
  syncLiveJiraRovo: (fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<JiraRovoSyncResult>("/api/integrations/jira-rovo/sync-live", {
      method: "POST",
      body: JSON.stringify({ fiscal_year: fiscalYear }),
    }),
  syncRoadmap: (fiscalYear = DEFAULT_FISCAL_YEAR, roadmapProjectKey = "ROADMAP") =>
    request<RoadmapSyncResult>(
      `/api/integrations/jira-rovo/roadmap/sync?fiscal_year=${fiscalYear}&roadmap_project_key=${encodeURIComponent(roadmapProjectKey)}`,
      {
        method: "POST",
      },
    ),
  roadmapItems: (fiscalYear = DEFAULT_FISCAL_YEAR) => request<RoadmapItem[]>(`/api/integrations/jira-rovo/roadmap/items?fiscal_year=${fiscalYear}`),
  updateRoadmapItemMapping: (itemId: number, payload: RoadmapItemMapPayload) =>
    request<RoadmapItem>(`/api/integrations/jira-rovo/roadmap/items/${itemId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  roadmapActuals: (fiscalYear = DEFAULT_FISCAL_YEAR, params: RoadmapActualParams = {}) =>
    request<RoadmapActualRow[]>(`/api/integrations/jira-rovo/roadmap/actuals?${roadmapActualQuery(fiscalYear, params)}`),
  roadmapActualGaps: (fiscalYear = DEFAULT_FISCAL_YEAR, params: RoadmapActualParams = {}) =>
    request<RoadmapActualRow[]>(`/api/integrations/jira-rovo/roadmap/actual-gaps?${roadmapActualQuery(fiscalYear, params)}`),
  forecastRecommendationDecisions: (fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<ForecastRecommendationDecision[]>(`/api/integrations/jira-rovo/roadmap/forecast-recommendation-decisions?fiscal_year=${fiscalYear}`),
  createForecastRecommendationDecision: (payload: ForecastRecommendationDecisionPayload) =>
    request<ForecastRecommendationDecision>("/api/integrations/jira-rovo/roadmap/forecast-recommendation-decisions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateRoadmapTicketMapping: (ticketKey: string, payload: RoadmapTicketMapPayload) =>
    request<RoadmapTicketMapResult>(`/api/integrations/jira-rovo/roadmap/ticket-links/${encodeURIComponent(ticketKey)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  attributionChanges: (limit = 50) =>
    request<AttributionChange[]>(`/api/integrations/jira-rovo/attribution-changes?limit=${limit}`),
  jiraIntegrationStatus: () => request<JiraIntegrationStatus>("/api/integrations/jira-rovo/status"),
  unmappedUsers: () => request<UnmappedUser[]>("/api/integrations/jira-rovo/unmapped-users"),
  unmappedProducts: () => request<UnmappedProduct[]>("/api/integrations/jira-rovo/unmapped-products"),
  userMappings: () => request<JiraUserMapping[]>("/api/integrations/jira-rovo/user-mappings"),
  productMappings: () => request<JiraProductMapping[]>("/api/integrations/jira-rovo/product-mappings"),
  jiraProjectCatalog: () => request<JiraProjectCatalog[]>("/api/integrations/jira-rovo/project-catalog"),
  updateJiraProjectCatalog: (projectId: number, payload: JiraProjectCatalogUpdatePayload) =>
    request<JiraProjectCatalog>(`/api/integrations/jira-rovo/project-catalog/${projectId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  refreshJiraProjectCatalog: () =>
    request<JiraProjectCatalogSyncResult>("/api/integrations/jira-rovo/project-catalog/refresh", {
      method: "POST",
    }),
  updateUserMapping: (mappingId: number, teamMemberId: number | null) =>
    request<JiraUserMapping>(`/api/integrations/jira-rovo/user-mappings/${mappingId}`, {
      method: "PUT",
      body: JSON.stringify({ team_member_id: teamMemberId }),
    }),
  syncRuns: () => request<SyncRun[]>("/api/integrations/jira-rovo/sync-runs"),
  worklogExclusions: () => request<JiraWorklogExclusionSummary>("/api/integrations/jira-rovo/worklog-exclusions"),
  estimationProfiles: () => request<EstimationProfile[]>("/api/estimations/profiles"),
  updateEstimationProfile: (profileId: number, payload: EstimationProfileUpdatePayload) =>
    request<EstimationProfile>(`/api/estimations/profiles/${profileId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  jiraTeamEstimationProfiles: () => request<JiraTeamEstimationProfile[]>("/api/estimations/jira-team-profiles"),
  createJiraTeamEstimationProfile: (payload: JiraTeamEstimationProfilePayload) =>
    request<JiraTeamEstimationProfile>("/api/estimations/jira-team-profiles", { method: "POST", body: JSON.stringify(payload) }),
  updateJiraTeamEstimationProfile: (profileId: number, payload: Partial<JiraTeamEstimationProfilePayload>) =>
    request<JiraTeamEstimationProfile>(`/api/estimations/jira-team-profiles/${profileId}`, { method: "PUT", body: JSON.stringify(payload) }),
  estimationRuns: (fiscalYear = DEFAULT_FISCAL_YEAR) => request<EstimationRun[]>(`/api/estimations/runs?fiscal_year=${fiscalYear}`),
  previewEstimation: (payload: EstimationRunRequest) =>
    request<EstimationPreview>("/api/estimations/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  runEstimation: (payload: EstimationRunRequest) =>
    request<EstimationPreview>("/api/estimations/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  reportedValues: (filters: { product_id?: number; team_member_id?: number } = {}, fiscalYear = DEFAULT_FISCAL_YEAR) => {
    const params = new URLSearchParams({ fiscal_year: String(fiscalYear) });
    if (filters.product_id !== undefined) params.set("product_id", String(filters.product_id));
    if (filters.team_member_id !== undefined) params.set("team_member_id", String(filters.team_member_id));
    return request<ReportedValueRow[]>(`/api/estimations/reported-values?${params.toString()}`);
  },
  estimationRunAllocations: (runId: number, limit = 100) =>
    request<EstimatedIssueAllocation[]>(`/api/estimations/runs/${runId}/allocations?limit=${limit}`),
  teamMemberStoryPointMetrics: (fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<TeamMemberStoryPointMetric[]>(`/api/estimations/story-point-metrics?fiscal_year=${fiscalYear}`),
  deliveryFlowIssues: (fiscalYear = DEFAULT_FISCAL_YEAR) => request<DeliveryFlowIssue[]>(`/api/estimations/delivery-flow?fiscal_year=${fiscalYear}`),
  laborCostReport: (fiscalYear = DEFAULT_FISCAL_YEAR, params: LaborCostReportParams) =>
    request<LaborCostReport>(`/api/reports/labor-cost?${laborCostReportQuery(fiscalYear, params)}`),
  exportLaborCostReport: (fiscalYear = DEFAULT_FISCAL_YEAR, params: LaborCostReportParams) =>
    download(`/api/reports/labor-cost.xlsx?${laborCostReportQuery(fiscalYear, params)}`, `sparc-labor-cost-FY${fiscalYear}.xlsx`),
};
