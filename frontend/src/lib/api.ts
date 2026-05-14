import type {
  BucketDistributionRow,
  DashboardSummary,
  ForecastResponse,
  ForecastUpsertPayload,
  JiraProductMapping,
  JiraRovoSyncResult,
  JiraUserMapping,
  Product,
  ProductBucketTables,
  ProductSummary,
  ProductSummaryRow,
  SyncRun,
  TeamImportResult,
  TeamMember,
  TeamMemberProducts,
  UnmappedProduct,
  UnmappedUser,
} from "../types/api";
import { appConfig } from "./config";

const API_BASE_URL = appConfig.apiBaseUrl;
const FISCAL_YEAR = appConfig.fiscalYear;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function upload<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  fiscalYear: FISCAL_YEAR,
  dashboardSummary: () => request<DashboardSummary>(`/api/dashboard/summary?fiscal_year=${FISCAL_YEAR}`),
  dashboardProducts: () => request<ProductSummaryRow[]>(`/api/dashboard/products?fiscal_year=${FISCAL_YEAR}`),
  productSummary: (productId: number) =>
    request<ProductSummary>(`/api/products/${productId}/summary?fiscal_year=${FISCAL_YEAR}`),
  bucketDistribution: (productId: number) =>
    request<BucketDistributionRow[]>(`/api/products/${productId}/bucket-distribution?fiscal_year=${FISCAL_YEAR}`),
  productBucketTables: (productId: number) =>
    request<ProductBucketTables>(`/api/products/${productId}/bucket-tables?fiscal_year=${FISCAL_YEAR}`),
  products: () => request<Product[]>("/api/products"),
  teamMembers: () => request<TeamMember[]>("/api/team-members"),
  updateTeamMember: (teamMemberId: number, payload: Partial<TeamMember>) =>
    request<TeamMember>(`/api/team-members/${teamMemberId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  teamMemberProducts: (teamMemberId: number) =>
    request<TeamMemberProducts>(`/api/team-members/${teamMemberId}/products?fiscal_year=${FISCAL_YEAR}`),
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
  unmappedUsers: () => request<UnmappedUser[]>("/api/integrations/jira-rovo/unmapped-users"),
  unmappedProducts: () => request<UnmappedProduct[]>("/api/integrations/jira-rovo/unmapped-products"),
  userMappings: () => request<JiraUserMapping[]>("/api/integrations/jira-rovo/user-mappings"),
  productMappings: () => request<JiraProductMapping[]>("/api/integrations/jira-rovo/product-mappings"),
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
};
