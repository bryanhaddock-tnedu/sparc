import { DatabaseZap, Download, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import { formatCurrency, formatHours } from "../lib/utils";
import type {
  Bucket,
  JiraIntegrationStatus,
  JiraProductMapping,
  JiraProjectCatalog,
  JiraUserMapping,
  Product,
  RoadmapActualRow,
  RoadmapItem,
  SyncRun,
  TeamMember,
} from "../types/api";

type RoadmapFilterState = {
  productId: string;
  teamMemberId: string;
  bucketId: string;
  monthSequence: string;
  programArea: string;
  mappingStatus: string;
};

type BillingSummaryRow = {
  id: string;
  label: string;
  programArea: string;
  product: string;
  roadmapItems: number;
  products: number;
  teamMembers: number;
  tickets: number;
  worklogs: number;
  actualHours: number;
  actualCost: number;
  gapTickets: number;
};

type RoadmapBillingSummary = {
  totals: {
    actualHours: number;
    actualCost: number;
    tickets: number;
    worklogs: number;
    gapTickets: number;
  };
  programAreas: BillingSummaryRow[];
  products: BillingSummaryRow[];
  roadmapItems: BillingSummaryRow[];
};

const EMPTY_ROADMAP_FILTERS: RoadmapFilterState = {
  productId: "",
  teamMemberId: "",
  bucketId: "",
  monthSequence: "",
  programArea: "",
  mappingStatus: "",
};

const UNASSIGNED_PROGRAM_AREA = "__unassigned";
const FISCAL_MONTH_LABELS = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"];

export function IntegrationsPage({ embedded = false }: { embedded?: boolean } = {}) {
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [buckets, setBuckets] = useState<Bucket[]>([]);
  const [userMappings, setUserMappings] = useState<JiraUserMapping[]>([]);
  const [productMappings, setProductMappings] = useState<JiraProductMapping[]>([]);
  const [jiraCatalog, setJiraCatalog] = useState<JiraProjectCatalog[]>([]);
  const [roadmapItems, setRoadmapItems] = useState<RoadmapItem[]>([]);
  const [roadmapActualRows, setRoadmapActualRows] = useState<RoadmapActualRow[]>([]);
  const [roadmapGaps, setRoadmapGaps] = useState<RoadmapActualRow[]>([]);
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [jiraStatus, setJiraStatus] = useState<JiraIntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [liveSyncing, setLiveSyncing] = useState(false);
  const [roadmapSyncing, setRoadmapSyncing] = useState(false);
  const [catalogRefreshing, setCatalogRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [roadmapFilters, setRoadmapFilters] = useState<RoadmapFilterState>(EMPTY_ROADMAP_FILTERS);

  async function loadData() {
    const monthSequence = roadmapFilters.monthSequence ? Number(roadmapFilters.monthSequence) : null;
    const [members, productRows, bucketRows, users, jiraProducts, catalogRows, roadmapRows, actualRows, gapRows, runs, status] = await Promise.all([
      api.teamMembers(),
      api.products(),
      api.buckets(),
      api.userMappings(),
      api.productMappings(),
      api.jiraProjectCatalog(),
      api.roadmapItems(),
      api.roadmapActuals(fiscalYear, { monthSequence }),
      api.roadmapActualGaps(fiscalYear, { monthSequence }),
      api.syncRuns(),
      api.jiraIntegrationStatus(),
    ]);
    setTeamMembers(members);
    setProducts(productRows);
    setBuckets(bucketRows);
    setUserMappings(users);
    setProductMappings(jiraProducts);
    setJiraCatalog(catalogRows);
    setRoadmapItems(roadmapRows);
    setRoadmapActualRows(actualRows);
    setRoadmapGaps(gapRows);
    setSyncRuns(runs);
    setJiraStatus(status);
  }

  useEffect(() => {
    setLoading(true);
    loadData()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load integration data"))
      .finally(() => setLoading(false));
  }, [fiscalYear, roadmapFilters.monthSequence]);

  async function runLiveSync() {
    setLiveSyncing(true);
    setError(null);
    setNotice(null);
    try {
      await api.syncLiveJiraRovo(fiscalYear);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run live Jira sync");
    } finally {
      setLiveSyncing(false);
    }
  }

  async function refreshCatalog() {
    setCatalogRefreshing(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.refreshJiraProjectCatalog();
      setJiraCatalog(result.projects);
      setNotice(`Jira project list refreshed: ${result.imported} projects available.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to refresh Jira project list");
    } finally {
      setCatalogRefreshing(false);
    }
  }

  async function runRoadmapSync() {
    setRoadmapSyncing(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.syncRoadmap();
      await loadData();
      setNotice(`Roadmap synced: ${result.roadmap_items} items and ${result.linked_issues} linked delivery tickets.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sync Jira roadmap");
    } finally {
      setRoadmapSyncing(false);
    }
  }

  async function updateUserMapping(mappingId: number, teamMemberId: number | null) {
    await api.updateUserMapping(mappingId, teamMemberId);
    await loadData();
  }

  async function updateProductMapping(mappingId: number, productId: number | null) {
    await api.updateProductMapping(mappingId, productId);
    await loadData();
  }

  async function updateRoadmapItemMapping(
    item: RoadmapItem,
    updates: Partial<Pick<RoadmapItem, "product_id" | "bucket_id" | "program_area">>,
  ) {
    setError(null);
    setNotice(null);
    try {
      const updatedItem = await api.updateRoadmapItemMapping(item.id, {
        product_id: updates.product_id !== undefined ? updates.product_id : item.product_id,
        bucket_id: updates.bucket_id !== undefined ? updates.bucket_id : item.bucket_id,
        program_area: updates.program_area !== undefined ? updates.program_area : item.program_area,
      });
      setRoadmapItems((current) => current.map((item) => (item.id === updatedItem.id ? updatedItem : item)));
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update Roadmap Item mapping");
    }
  }

  async function updateRoadmapTicketMapping(ticketKey: string, roadmapItemId: number | null) {
    setError(null);
    setNotice(null);
    try {
      await api.updateRoadmapTicketMapping(ticketKey, { roadmap_item_id: roadmapItemId });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update ticket Roadmap Item mapping");
    }
  }

  function updateRoadmapFilter(key: keyof RoadmapFilterState, value: string) {
    setRoadmapFilters((current) => ({ ...current, [key]: value }));
  }

  function resetRoadmapFilters() {
    setRoadmapFilters(EMPTY_ROADMAP_FILTERS);
  }

  function exportRoadmapSummary() {
    downloadCsv(`sparc-roadmap-billing-${fiscalYearLabel.toLowerCase()}.csv`, roadmapBillingSummaryCsvRows(billingSummary));
  }

  function exportRoadmapGaps() {
    downloadCsv(`sparc-roadmap-gaps-${fiscalYearLabel.toLowerCase()}.csv`, roadmapGapCsvRows(roadmapGapTickets));
  }

  const catalogLastCheckedAt = useMemo(() => latestCatalogCheckedAt(jiraCatalog), [jiraCatalog]);
  const sortedRoadmapItems = useMemo(() => sortRoadmapItems(roadmapItems), [roadmapItems]);
  const programAreaOptions = useMemo(() => programAreaOptionsFrom(roadmapActualRows, roadmapItems), [roadmapActualRows, roadmapItems]);
  const visibleRoadmapActualRows = useMemo(() => filterRoadmapActualRows(roadmapActualRows, roadmapFilters), [roadmapActualRows, roadmapFilters]);
  const visibleRoadmapGapRows = useMemo(() => filterRoadmapActualRows(roadmapGaps, roadmapFilters), [roadmapGaps, roadmapFilters]);
  const roadmapGapTickets = useMemo(() => expandRoadmapGapTickets(visibleRoadmapGapRows), [visibleRoadmapGapRows]);
  const billingSummary = useMemo(() => buildRoadmapBillingSummary(visibleRoadmapActualRows), [visibleRoadmapActualRows]);

  if (loading) return <LoadingBlock />;
  if (error && !jiraStatus) return <ErrorBlock message={error} />;

  const unmappedUserCount = userMappings.filter((mapping) => mapping.team_member_id === null).length;
  const unmappedProductCount = productMappings.filter((mapping) => mapping.product_id === null).length;
  const unmappedRoadmapCount = roadmapItems.filter((item) => item.product_id === null || item.bucket_id === null).length;

  return (
    <div className="space-y-5">
      <section className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end">
        <div>
          {embedded ? <h2 className="text-xl font-semibold">Jira Sync</h2> : <h1 className="text-2xl font-semibold">Jira Sync</h1>}
          <p className="mt-1 text-sm text-muted-foreground">
            Live Jira actual-hours sync for {fiscalYearLabel} ({fiscalYearRangeLabel}). Roadmap Item mapping is global.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:items-end">
          {embedded ? null : <PageNav current="admin" />}
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button onClick={runRoadmapSync} disabled={roadmapSyncing || !jiraStatus?.configured} variant="outline">
              <RefreshCw className={`h-4 w-4 ${roadmapSyncing ? "animate-spin" : ""}`} />
              {roadmapSyncing ? "Syncing Roadmap" : "Sync Roadmap"}
            </Button>
            <Button onClick={runLiveSync} disabled={liveSyncing || !jiraStatus?.configured}>
              <DatabaseZap className={`h-4 w-4 ${liveSyncing ? "animate-pulse" : ""}`} />
              {liveSyncing ? "Syncing Jira" : "Sync Jira Actuals"}
            </Button>
          </div>
        </div>
      </section>

      {notice ? <div className="rounded-md border border-[color:var(--spark-cyan)] bg-accent/10 px-3 py-2 text-sm text-primary">{notice}</div> : null}
      {error ? <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <StatusCard label="Jira config" value={jiraStatus?.configured ? "Ready" : "Missing"} tone={jiraStatus?.configured ? "good" : "warn"} />
        <ProjectListStatusCard
          count={jiraCatalog.length}
          disabled={!jiraStatus?.configured}
          lastCheckedAt={catalogLastCheckedAt}
          refreshing={catalogRefreshing}
          onRefresh={refreshCatalog}
        />
        <StatusCard label="User mappings" value={`${userMappings.length - unmappedUserCount}/${userMappings.length}`} />
        <StatusCard label="Product mappings" value={`${productMappings.length - unmappedProductCount}/${productMappings.length}`} />
        <StatusCard label="Roadmap Items" value={`${roadmapItems.length - unmappedRoadmapCount}/${roadmapItems.length}`} />
        <StatusCard label="Latest sync" value={syncRuns[0]?.status ?? "No runs"} />
      </section>

      <RoadmapBillingFilters
        buckets={buckets}
        filters={roadmapFilters}
        fiscalYear={fiscalYear}
        programAreas={programAreaOptions}
        products={products}
        teamMembers={teamMembers}
        onChange={updateRoadmapFilter}
        onReset={resetRoadmapFilters}
      />

      <RoadmapBillingSummarySection
        summary={billingSummary}
        onExportGaps={exportRoadmapGaps}
        onExportSummary={exportRoadmapSummary}
      />

      {!jiraStatus?.configured ? (
        <div className="rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm">
          <div className="font-medium text-foreground">Live Jira sync is waiting on server configuration.</div>
          <div className="mt-1 text-muted-foreground">
            Missing: {jiraStatus?.missing.join(", ") || "Jira environment variables"}. These stay server-side and should come from local env or Key Vault.
          </div>
        </div>
      ) : null}

      <MappingTable title="Jira Users" unmapped={unmappedUserCount}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Jira User</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Team Member</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {userMappings.map((mapping) => (
              <TableRow key={mapping.id}>
                <TableCell>{mapping.jira_display_name}</TableCell>
                <TableCell>{mapping.jira_email ?? ""}</TableCell>
                <TableCell>
                  <select
                    className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={mapping.team_member_id ?? ""}
                    onChange={(event) => void updateUserMapping(mapping.id, event.target.value ? Number(event.target.value) : null)}
                  >
                    <option value="">Unmapped / external</option>
                    {teamMembers.map((member) => (
                      <option key={member.id} value={member.id}>
                        {member.name}
                      </option>
                    ))}
                  </select>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </MappingTable>

      <MappingTable title="Jira Products" unmapped={unmappedProductCount}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Jira Project</TableHead>
              <TableHead>Key</TableHead>
              <TableHead>Product</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {productMappings.map((mapping) => (
              <TableRow key={mapping.id}>
                <TableCell>{mapping.jira_project_name}</TableCell>
                <TableCell>{mapping.jira_project_key}</TableCell>
                <TableCell>
                  <select
                    className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={mapping.product_id ?? ""}
                    onChange={(event) => void updateProductMapping(mapping.id, event.target.value ? Number(event.target.value) : null)}
                  >
                    <option value="">Unmapped</option>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name}
                      </option>
                    ))}
                  </select>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </MappingTable>

      <MappingTable title="Roadmap Items" unmapped={unmappedRoadmapCount}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Roadmap Item</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Tickets</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Bucket</TableHead>
              <TableHead>Program Area</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedRoadmapItems.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <div className="font-medium text-primary">
                    {item.source_url ? (
                      <a href={item.source_url} target="_blank" rel="noreferrer">
                        {item.jira_issue_key}
                      </a>
                    ) : (
                      item.jira_issue_key
                    )}
                  </div>
                  <div className="max-w-[28rem] truncate text-sm text-foreground" title={item.title}>
                    {item.title}
                  </div>
                  {item.program_area ? <div className="text-xs text-muted-foreground">{item.program_area}</div> : null}
                </TableCell>
                <TableCell>{item.status ?? ""}</TableCell>
                <TableCell className="numeric-cell">{item.linked_issue_count}</TableCell>
                <TableCell>
                  <select
                    className="h-9 w-full min-w-52 rounded-md border border-input bg-background px-2 text-sm"
                    value={item.product_id ?? ""}
                    onChange={(event) =>
                      void updateRoadmapItemMapping(item, { product_id: event.target.value ? Number(event.target.value) : null })
                    }
                  >
                    <option value="">Unmapped</option>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name}
                      </option>
                    ))}
                  </select>
                </TableCell>
                <TableCell>
                  <select
                    className="h-9 w-full min-w-40 rounded-md border border-input bg-background px-2 text-sm"
                    value={item.bucket_id ?? ""}
                    onChange={(event) =>
                      void updateRoadmapItemMapping(item, { bucket_id: event.target.value ? Number(event.target.value) : null })
                    }
                  >
                    <option value="">Unmapped</option>
                    {buckets.map((bucket) => (
                      <option key={bucket.id} value={bucket.id}>
                        {bucket.name}
                      </option>
                    ))}
                  </select>
                </TableCell>
                <TableCell>
                  <input
                    className="h-9 w-full min-w-44 rounded-md border border-input bg-background px-2 text-sm"
                    defaultValue={item.program_area ?? ""}
                    key={`${item.id}-${item.program_area ?? ""}`}
                    onBlur={(event) => {
                      const nextProgramArea = event.currentTarget.value.trim() || null;
                      if (nextProgramArea !== (item.program_area ?? null)) {
                        void updateRoadmapItemMapping(item, { program_area: nextProgramArea });
                      }
                    }}
                    placeholder="Program area"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </MappingTable>

      <MappingTable title="Roadmap Actual Gaps" unmapped={roadmapGapTickets.length} badgeLabel="gaps">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ticket</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Team Member</TableHead>
              <TableHead>Bucket</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Roadmap Item</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {roadmapGapTickets.length ? (
              roadmapGapTickets.map((gap) => (
                <TableRow key={gap.key}>
                  <TableCell>
                    <div className="font-medium text-primary">{gap.ticketKey}</div>
                    <div className="text-xs text-muted-foreground">
                      {formatHours(gap.row.actual_hours)} / {formatCurrency(gap.row.actual_cost)}
                    </div>
                  </TableCell>
                  <TableCell>{gap.row.product}</TableCell>
                  <TableCell>{gap.row.team_member}</TableCell>
                  <TableCell>{gap.row.bucket}</TableCell>
                  <TableCell>
                    <Badge className={gap.row.mapping_status === "ambiguous" ? "border-warning/50 text-warning" : "border-muted text-muted-foreground"}>
                      {gap.row.mapping_status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <select
                      className="h-9 w-full min-w-64 rounded-md border border-input bg-background px-2 text-sm"
                      defaultValue=""
                      onChange={(event) => void updateRoadmapTicketMapping(gap.ticketKey, event.target.value ? Number(event.target.value) : null)}
                    >
                      <option value="">Map to Roadmap Item</option>
                      {sortedRoadmapItems.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.jira_issue_key} - {item.title}
                        </option>
                      ))}
                    </select>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell className="py-6 text-sm text-muted-foreground" colSpan={6}>
                  No Roadmap Actual gaps for {fiscalYearLabel}.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </MappingTable>

      <Card>
        <CardHeader>
          <CardTitle>Sync History</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Status</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Imported</TableHead>
                <TableHead>Skipped</TableHead>
                <TableHead>Completed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {syncRuns.map((run) => (
                <TableRow key={run.id}>
                  <TableCell>
                    <Badge className={run.status === "completed" ? "border-primary/40 text-primary" : "border-destructive/40 text-destructive"}>
                      {run.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{run.source}</TableCell>
                  <TableCell className="numeric-cell">{run.imported_count}</TableCell>
                  <TableCell className="numeric-cell">{run.skipped_count}</TableCell>
                  <TableCell>{run.completed_at ? formatDate(run.completed_at) : ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function ProjectListStatusCard({
  count,
  disabled,
  lastCheckedAt,
  refreshing,
  onRefresh,
}: {
  count: number;
  disabled: boolean;
  lastCheckedAt: string | null;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  return (
    <Card className="min-h-[118px]">
      <CardHeader className="flex flex-row items-start justify-between gap-2 p-4 pb-0">
        <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">Project list</CardTitle>
        <Button
          aria-label="Refresh Jira project list"
          className="h-7 w-7"
          disabled={disabled || refreshing}
          size="icon"
          title="Refresh Jira project list"
          variant="ghost"
          onClick={onRefresh}
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
        </Button>
      </CardHeader>
      <CardContent className="flex min-h-[72px] flex-col items-center justify-center p-4 pt-2">
        <div className="numeric-cell text-center text-2xl font-semibold leading-none text-foreground sm:text-3xl">{count}</div>
        <div className="mt-2 text-center text-xs leading-tight text-muted-foreground">
          {lastCheckedAt ? `Last refreshed ${formatDateTime(lastCheckedAt)}` : "Not refreshed yet"}
        </div>
      </CardContent>
    </Card>
  );
}

function StatusCard({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "good" | "warn" }) {
  const valueClass = tone === "good" ? "text-primary" : tone === "warn" ? "text-warning" : "text-foreground";
  return (
    <Card className="min-h-[118px]">
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-[72px] items-center justify-center p-4 pt-2">
        <div className={`numeric-cell text-center text-2xl font-semibold leading-none sm:text-3xl ${valueClass}`}>{value}</div>
      </CardContent>
    </Card>
  );
}

function RoadmapBillingFilters({
  buckets,
  filters,
  fiscalYear,
  products,
  programAreas,
  teamMembers,
  onChange,
  onReset,
}: {
  buckets: Bucket[];
  filters: RoadmapFilterState;
  fiscalYear: number;
  products: Product[];
  programAreas: string[];
  teamMembers: TeamMember[];
  onChange: (key: keyof RoadmapFilterState, value: string) => void;
  onReset: () => void;
}) {
  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-7">
        <FilterSelect label="Product" value={filters.productId} onChange={(value) => onChange("productId", value)}>
          <option value="">All products</option>
          {products.map((product) => (
            <option key={product.id} value={product.id}>
              {product.name}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect label="Team Member" value={filters.teamMemberId} onChange={(value) => onChange("teamMemberId", value)}>
          <option value="">All team members</option>
          {teamMembers.map((member) => (
            <option key={member.id} value={member.id}>
              {member.name}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect label="Bucket" value={filters.bucketId} onChange={(value) => onChange("bucketId", value)}>
          <option value="">All buckets</option>
          {buckets.map((bucket) => (
            <option key={bucket.id} value={bucket.id}>
              {bucket.name}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect label="Month" value={filters.monthSequence} onChange={(value) => onChange("monthSequence", value)}>
          <option value="">Entire FY</option>
          {fiscalMonthOptions(fiscalYear).map((month) => (
            <option key={month.sequence} value={month.sequence}>
              {month.label}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect label="Program Area" value={filters.programArea} onChange={(value) => onChange("programArea", value)}>
          <option value="">All program areas</option>
          <option value={UNASSIGNED_PROGRAM_AREA}>Unassigned</option>
          {programAreas.map((programArea) => (
            <option key={programArea} value={programArea}>
              {programArea}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect label="Status" value={filters.mappingStatus} onChange={(value) => onChange("mappingStatus", value)}>
          <option value="">All statuses</option>
          <option value="mapped">Mapped</option>
          <option value="unmapped">Unmapped</option>
          <option value="ambiguous">Ambiguous</option>
        </FilterSelect>
        <div className="flex items-end">
          <Button className="h-9 w-full" type="button" variant="outline" onClick={onReset}>
            Reset
          </Button>
        </div>
      </div>
    </section>
  );
}

function FilterSelect({ children, label, value, onChange }: { children: ReactNode; label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="space-y-1">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <select className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  );
}

function RoadmapBillingSummarySection({
  summary,
  onExportGaps,
  onExportSummary,
}: {
  summary: RoadmapBillingSummary;
  onExportGaps: () => void;
  onExportSummary: () => void;
}) {
  return (
    <section className="space-y-3 rounded-lg border bg-card p-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <h2 className="text-lg font-semibold">Roadmap Billing Summary</h2>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button type="button" variant="outline" onClick={onExportSummary}>
            <Download className="h-4 w-4" />
            Summary CSV
          </Button>
          <Button type="button" variant="outline" onClick={onExportGaps}>
            <Download className="h-4 w-4" />
            Gaps CSV
          </Button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <SummaryMetric label="Hours" value={formatHours(summary.totals.actualHours)} />
        <SummaryMetric label="Cost" value={formatCurrency(summary.totals.actualCost)} />
        <SummaryMetric label="Tickets" value={String(summary.totals.tickets)} />
        <SummaryMetric label="Worklogs" value={String(summary.totals.worklogs)} />
        <SummaryMetric label="Gap Tickets" value={String(summary.totals.gapTickets)} tone={summary.totals.gapTickets ? "warn" : "default"} />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <BillingSummaryTable rows={summary.programAreas} title="Program Areas" />
        <BillingSummaryTable rows={summary.products} title="Products" />
      </div>
      <BillingSummaryTable rows={summary.roadmapItems} title="Roadmap Items" />
    </section>
  );
}

function SummaryMetric({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "warn" }) {
  return (
    <div className="rounded-md bg-secondary px-3 py-2">
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <div className={`numeric-cell text-lg font-semibold ${tone === "warn" ? "text-warning" : "text-primary"}`}>{value}</div>
    </div>
  );
}

function BillingSummaryTable({ rows, title }: { rows: BillingSummaryRow[]; title: string }) {
  return (
    <section className="overflow-hidden rounded-lg border">
      <div className="border-b bg-secondary/50 px-3 py-2 text-sm font-semibold">{title}</div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Program Area</TableHead>
              <TableHead className="text-right">Tickets</TableHead>
              <TableHead className="text-right">Hours</TableHead>
              <TableHead className="text-right">Cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length ? (
              rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-medium">{row.label}</TableCell>
                  <TableCell>{row.product}</TableCell>
                  <TableCell>{row.programArea}</TableCell>
                  <TableCell className="numeric-cell text-right">{row.tickets}</TableCell>
                  <TableCell className="numeric-cell text-right font-semibold">{formatHours(row.actualHours)}</TableCell>
                  <TableCell className="numeric-cell text-right font-semibold text-primary">{formatCurrency(row.actualCost)}</TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell className="py-5 text-sm text-muted-foreground" colSpan={6}>
                  No billing actuals match the selected filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

function MappingTable({ title, unmapped, badgeLabel = "unmapped", children }: { title: string; unmapped: number; badgeLabel?: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{title}</h2>
        <Badge className={unmapped ? "border-destructive/40 text-destructive" : "border-primary/40 text-primary"}>
          {unmapped} {badgeLabel}
        </Badge>
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="overflow-x-auto">{children}</div>
      </div>
    </section>
  );
}

function sortRoadmapItems(items: RoadmapItem[]) {
  return [...items].sort((left, right) => {
    const leftUnmapped = left.product_id === null || left.bucket_id === null;
    const rightUnmapped = right.product_id === null || right.bucket_id === null;
    if (leftUnmapped !== rightUnmapped) return leftUnmapped ? -1 : 1;
    return left.jira_issue_key.localeCompare(right.jira_issue_key);
  });
}

function expandRoadmapGapTickets(rows: RoadmapActualRow[]) {
  return rows.flatMap((row) =>
    row.ticket_keys.map((ticketKey) => ({
      key: `${row.mapping_status}:${row.product_id}:${row.team_member_id}:${row.bucket_id}:${ticketKey}`,
      ticketKey,
      row,
    })),
  );
}

function filterRoadmapActualRows(rows: RoadmapActualRow[], filters: RoadmapFilterState) {
  return rows.filter((row) => {
    if (filters.productId && row.product_id !== Number(filters.productId)) return false;
    if (filters.teamMemberId && row.team_member_id !== Number(filters.teamMemberId)) return false;
    if (filters.bucketId && row.bucket_id !== Number(filters.bucketId)) return false;
    if (filters.mappingStatus && row.mapping_status !== filters.mappingStatus) return false;
    if (filters.programArea === UNASSIGNED_PROGRAM_AREA && row.program_area) return false;
    if (filters.programArea && filters.programArea !== UNASSIGNED_PROGRAM_AREA && row.program_area !== filters.programArea) return false;
    return true;
  });
}

function programAreaOptionsFrom(rows: RoadmapActualRow[], items: RoadmapItem[]) {
  const values = new Set<string>();
  rows.forEach((row) => {
    if (row.program_area) values.add(row.program_area);
  });
  items.forEach((item) => {
    if (item.program_area) values.add(item.program_area);
  });
  return Array.from(values).sort((left, right) => left.localeCompare(right));
}

function fiscalMonthOptions(fiscalYear: number) {
  return FISCAL_MONTH_LABELS.map((month, index) => {
    const sequence = index + 1;
    const calendarYear = sequence <= 6 ? fiscalYear - 1 : fiscalYear;
    return { sequence, label: `${month} ${calendarYear}` };
  });
}

function buildRoadmapBillingSummary(rows: RoadmapActualRow[]): RoadmapBillingSummary {
  const programAreas = new Map<string, BillingSummaryAccumulator>();
  const products = new Map<string, BillingSummaryAccumulator>();
  const roadmapItems = new Map<string, BillingSummaryAccumulator>();
  const totals = newAccumulator("totals", "Totals");

  rows.forEach((row) => {
    addRowToAccumulator(totals, row);

    const programAreaKey = row.program_area || UNASSIGNED_PROGRAM_AREA;
    addRowToAccumulator(ensureAccumulator(programAreas, programAreaKey, row.program_area || "Unassigned"), row);

    const productKey = String(row.product_id);
    addRowToAccumulator(ensureAccumulator(products, productKey, row.product), row);

    const roadmapItemKey = row.roadmap_item_id ? String(row.roadmap_item_id) : row.mapping_status;
    const roadmapItemLabel =
      row.mapping_status === "mapped"
        ? `${row.roadmap_item_key ?? "Roadmap Item"} - ${row.roadmap_item_title ?? "Untitled"}`
        : row.mapping_status === "ambiguous"
          ? "Ambiguous Roadmap Mapping"
          : "Unmapped Roadmap Item";
    addRowToAccumulator(ensureAccumulator(roadmapItems, roadmapItemKey, roadmapItemLabel), row);
  });

  return {
    totals: {
      actualHours: totals.actualHours,
      actualCost: totals.actualCost,
      tickets: totals.tickets.size,
      worklogs: totals.worklogs,
      gapTickets: totals.gapTickets.size,
    },
    programAreas: finalizeSummaryRows(programAreas, "program"),
    products: finalizeSummaryRows(products, "product"),
    roadmapItems: finalizeSummaryRows(roadmapItems, "roadmap"),
  };
}

type BillingSummaryAccumulator = {
  id: string;
  label: string;
  programAreas: Set<string>;
  products: Set<string>;
  roadmapItems: Set<string>;
  teamMembers: Set<string>;
  tickets: Set<string>;
  gapTickets: Set<string>;
  worklogs: number;
  actualHours: number;
  actualCost: number;
};

function newAccumulator(id: string, label: string): BillingSummaryAccumulator {
  return {
    id,
    label,
    programAreas: new Set(),
    products: new Set(),
    roadmapItems: new Set(),
    teamMembers: new Set(),
    tickets: new Set(),
    gapTickets: new Set(),
    worklogs: 0,
    actualHours: 0,
    actualCost: 0,
  };
}

function ensureAccumulator(map: Map<string, BillingSummaryAccumulator>, id: string, label: string) {
  const existing = map.get(id);
  if (existing) return existing;
  const created = newAccumulator(id, label);
  map.set(id, created);
  return created;
}

function addRowToAccumulator(accumulator: BillingSummaryAccumulator, row: RoadmapActualRow) {
  accumulator.programAreas.add(row.program_area || "Unassigned");
  accumulator.products.add(row.product);
  accumulator.roadmapItems.add(row.roadmap_item_key || row.mapping_status);
  accumulator.teamMembers.add(row.team_member);
  row.ticket_keys.forEach((ticketKey) => {
    accumulator.tickets.add(ticketKey);
    if (row.mapping_status !== "mapped") accumulator.gapTickets.add(ticketKey);
  });
  accumulator.worklogs += row.worklog_count;
  accumulator.actualHours += row.actual_hours;
  accumulator.actualCost += row.actual_cost;
}

function finalizeSummaryRows(map: Map<string, BillingSummaryAccumulator>, mode: "program" | "product" | "roadmap") {
  return Array.from(map.values())
    .map((row) => ({
      id: row.id,
      label: row.label,
      programArea: mode === "program" ? row.label : displaySet(row.programAreas, "program areas"),
      product: mode === "product" ? row.label : displaySet(row.products, "products"),
      roadmapItems: row.roadmapItems.size,
      products: row.products.size,
      teamMembers: row.teamMembers.size,
      tickets: row.tickets.size,
      worklogs: row.worklogs,
      actualHours: row.actualHours,
      actualCost: row.actualCost,
      gapTickets: row.gapTickets.size,
    }))
    .sort((left, right) => right.actualCost - left.actualCost || left.label.localeCompare(right.label));
}

function displaySet(values: Set<string>, noun: string) {
  if (values.size === 0) return "";
  if (values.size === 1) return Array.from(values)[0];
  return `${values.size} ${noun}`;
}

function roadmapBillingSummaryCsvRows(summary: RoadmapBillingSummary) {
  const rows: Array<Array<string | number>> = [
    ["section", "name", "product", "program_area", "roadmap_items", "products", "team_members", "tickets", "worklogs", "gap_tickets", "actual_hours", "actual_cost"],
  ];
  addSummaryCsvRows(rows, "program_area", summary.programAreas);
  addSummaryCsvRows(rows, "product", summary.products);
  addSummaryCsvRows(rows, "roadmap_item", summary.roadmapItems);
  return rows;
}

function addSummaryCsvRows(rows: Array<Array<string | number>>, section: string, summaryRows: BillingSummaryRow[]) {
  summaryRows.forEach((row) => {
    rows.push([
      section,
      row.label,
      row.product,
      row.programArea,
      row.roadmapItems,
      row.products,
      row.teamMembers,
      row.tickets,
      row.worklogs,
      row.gapTickets,
      roundCsvNumber(row.actualHours),
      roundCsvNumber(row.actualCost),
    ]);
  });
}

function roadmapGapCsvRows(gaps: ReturnType<typeof expandRoadmapGapTickets>) {
  return [
    ["ticket_key", "mapping_status", "product", "team_member", "bucket", "program_area", "group_ticket_count", "group_hours", "group_cost"],
    ...gaps.map((gap) => [
      gap.ticketKey,
      gap.row.mapping_status,
      gap.row.product,
      gap.row.team_member,
      gap.row.bucket,
      gap.row.program_area ?? "Unassigned",
      gap.row.ticket_count,
      roundCsvNumber(gap.row.actual_hours),
      roundCsvNumber(gap.row.actual_cost),
    ]),
  ];
}

function downloadCsv(filename: string, rows: Array<Array<string | number>>) {
  const csv = rows.map((row) => row.map(csvCell).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: string | number) {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function roundCsvNumber(value: number) {
  return Math.round(value * 100) / 100;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function latestCatalogCheckedAt(projects: JiraProjectCatalog[]) {
  const timestamps = projects.map((project) => Date.parse(project.last_checked_at)).filter(Number.isFinite);
  if (!timestamps.length) return null;
  return new Date(Math.max(...timestamps)).toISOString();
}
