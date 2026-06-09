import type {
  AdminDataExportOption,
  AdminDataImportResult,
  AuthStatus,
  BucketDistributionRow,
  DashboardLaborMix,
  DashboardSummary,
  DashboardWorkTypeRow,
  EstimatedIssueAllocation,
  EstimationPreview,
  EstimationProfile,
  EstimationProfileUpdatePayload,
  EstimationRun,
  EstimationRunRequest,
  ForecastResponse,
  ForecastUpsertPayload,
  JiraIntegrationStatus,
  JiraProductMapping,
  JiraProjectCatalog,
  JiraProjectCatalogSyncResult,
  JiraProjectCatalogUpdatePayload,
  JiraRovoSyncResult,
  JiraUserMapping,
  Product,
  ProductBucketTables,
  ProductCreatePayload,
  ProductJiraSpace,
  ProductJiraSpacePayload,
  ProductJiraSpaceUpdatePayload,
  ProductSummary,
  ProductSummaryRow,
  ProductTeamMember,
  ProductTeamMemberPayload,
  ProductTeamMemberUpdatePayload,
  ReportedValueRow,
  SyncRun,
  SystemScanResult,
  TeamImportResult,
  TeamMember,
  TeamMemberActualWorklog,
  TeamMemberProducts,
  UnmappedProduct,
  UnmappedUser,
} from "../types/api";
import { appConfig } from "./config";

const API_BASE_URL = appConfig.apiBaseUrl;
const DEFAULT_FISCAL_YEAR = appConfig.fiscalYear;

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

async function download(path: string): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE_URL}${path}`, { credentials: "include" });
  if (!response.ok) {
    const message = await responseErrorMessage(response);
    throw new Error(message || `Request failed with ${response.status}`);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  const filename = match?.[1] ?? "sparc-admin-data.zip";
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
  exportAdminData: (datasets: string[]) => {
    const params = new URLSearchParams();
    datasets.forEach((dataset) => params.append("datasets", dataset));
    return download(`/api/admin-data/export${params.toString() ? `?${params.toString()}` : ""}`);
  },
  importAdminData: (file: File, datasets: string[]) => {
    const params = new URLSearchParams();
    datasets.forEach((dataset) => params.append("datasets", dataset));
    const formData = new FormData();
    formData.append("file", file);
    return upload<AdminDataImportResult>(`/api/admin-data/import${params.toString() ? `?${params.toString()}` : ""}`, formData);
  },
  dashboardSummary: (fiscalYear = DEFAULT_FISCAL_YEAR) => request<DashboardSummary>(`/api/dashboard/summary?fiscal_year=${fiscalYear}`),
  dashboardProducts: (fiscalYear = DEFAULT_FISCAL_YEAR) => request<ProductSummaryRow[]>(`/api/dashboard/products?fiscal_year=${fiscalYear}`),
  dashboardWorkTypes: (fiscalYear = DEFAULT_FISCAL_YEAR) => request<DashboardWorkTypeRow[]>(`/api/dashboard/work-types?fiscal_year=${fiscalYear}`),
  dashboardLaborMix: (fiscalYear = DEFAULT_FISCAL_YEAR) => request<DashboardLaborMix>(`/api/dashboard/labor-mix?fiscal_year=${fiscalYear}`),
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
  productSummary: (productId: number, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<ProductSummary>(`/api/products/${productId}/summary?fiscal_year=${fiscalYear}`),
  bucketDistribution: (productId: number, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<BucketDistributionRow[]>(`/api/products/${productId}/bucket-distribution?fiscal_year=${fiscalYear}`),
  productBucketTables: (productId: number, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<ProductBucketTables>(`/api/products/${productId}/bucket-tables?fiscal_year=${fiscalYear}`),
  products: (fiscalYear = DEFAULT_FISCAL_YEAR) => request<Product[]>(`/api/products?fiscal_year=${fiscalYear}`),
  createProduct: (payload: ProductCreatePayload, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<Product>(`/api/products?fiscal_year=${fiscalYear}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProduct: (
    productId: number,
    payload: Partial<Pick<Product, "name" | "jira_space_key" | "description" | "budget_amount" | "is_active">>,
    fiscalYear = DEFAULT_FISCAL_YEAR,
  ) =>
    request<Product>(`/api/products/${productId}?fiscal_year=${fiscalYear}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteProduct: (productId: number) =>
    request<{ message: string }>(`/api/products/${productId}`, {
      method: "DELETE",
    }),
  productTeamMembers: (productId: number) => request<ProductTeamMember[]>(`/api/products/${productId}/team-members`),
  addProductTeamMember: (productId: number, payload: ProductTeamMemberPayload) =>
    request<ProductTeamMember>(`/api/products/${productId}/team-members`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProductTeamMember: (productId: number, assignmentId: number, payload: ProductTeamMemberUpdatePayload) =>
    request<ProductTeamMember>(`/api/products/${productId}/team-members/${assignmentId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  removeProductTeamMember: (productId: number, assignmentId: number) =>
    request<{ message: string }>(`/api/products/${productId}/team-members/${assignmentId}`, {
      method: "DELETE",
    }),
  productJiraSpaces: (productId: number) => request<ProductJiraSpace[]>(`/api/products/${productId}/jira-spaces`),
  addProductJiraSpace: (productId: number, payload: ProductJiraSpacePayload) =>
    request<ProductJiraSpace>(`/api/products/${productId}/jira-spaces`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProductJiraSpace: (productId: number, spaceId: number, payload: ProductJiraSpaceUpdatePayload) =>
    request<ProductJiraSpace>(`/api/products/${productId}/jira-spaces/${spaceId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  removeProductJiraSpace: (productId: number, spaceId: number) =>
    request<{ message: string }>(`/api/products/${productId}/jira-spaces/${spaceId}`, {
      method: "DELETE",
    }),
  validateProductJiraSpace: (productId: number, spaceId: number) =>
    request<ProductJiraSpace>(`/api/products/${productId}/jira-spaces/${spaceId}/validate`, {
      method: "POST",
    }),
  teamMembers: () => request<TeamMember[]>("/api/team-members"),
  updateTeamMember: (teamMemberId: number, payload: Partial<TeamMember>) =>
    request<TeamMember>(`/api/team-members/${teamMemberId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  teamMemberProducts: (teamMemberId: number, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<TeamMemberProducts>(`/api/team-members/${teamMemberId}/products?fiscal_year=${fiscalYear}`),
  teamMemberActualWorklogs: (teamMemberId: number, fiscalYear = DEFAULT_FISCAL_YEAR) =>
    request<TeamMemberActualWorklog[]>(`/api/team-members/${teamMemberId}/actual-worklogs?fiscal_year=${fiscalYear}`),
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
  updateProductMapping: (mappingId: number, productId: number | null) =>
    request<JiraProductMapping>(`/api/integrations/jira-rovo/product-mappings/${mappingId}`, {
      method: "PUT",
      body: JSON.stringify({ product_id: productId }),
    }),
  syncRuns: () => request<SyncRun[]>("/api/integrations/jira-rovo/sync-runs"),
  estimationProfiles: () => request<EstimationProfile[]>("/api/estimations/profiles"),
  updateEstimationProfile: (profileId: number, payload: EstimationProfileUpdatePayload) =>
    request<EstimationProfile>(`/api/estimations/profiles/${profileId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
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
};
