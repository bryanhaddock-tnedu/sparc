import { CheckCircle2, DatabaseZap, Download, RefreshCw, XCircle } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { TeamMemberNameLink } from "../components/TeamMemberNameLink";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { fiscalYearRangeLabel as formatFiscalYearRangeLabel, useFiscalYear } from "../lib/fiscalYear";
import { formatCurrency, formatHours } from "../lib/utils";
import type {
  AttributionChange,
  Bucket,
  ForecastRecommendationAction,
  ForecastRecommendationDecision,
  JiraIntegrationStatus,
  JiraProductMapping,
  JiraProjectCatalog,
  JiraUserMapping,
  Product,
  ReportedValueRow,
  RoadmapActualRow,
  RoadmapItem,
  RoadmapItemCandidate,
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

type RoadmapForecastComparisonRow = {
  id: string;
  productId: number;
  bucketId: number;
  product: string;
  bucket: string;
  programAreas: string;
  roadmapItems: number;
  teamMembers: number;
  tickets: number;
  gapTickets: number;
  worklogs: number;
  forecastHours: number;
  actualHours: number;
  actualCost: number;
  remainingHours: number;
  percentUsed: number | null;
  suggestedDeltaHours: number;
  suggestedForecastHours: number;
  recommendation: "none" | "monitor" | "resolve_gaps" | "add_forecast" | "increase_forecast";
  status: "on_track" | "near_forecast" | "over_forecast" | "no_forecast" | "mapping_gaps";
};

type ForecastRecommendationTarget = {
  teamMemberId: string;
  monthSequence: string;
  note: string;
};

type RoadmapItemMappingSummary = {
  total: number;
  mapped: number;
  needsMapping: number;
  needsProduct: number;
  needsBucket: number;
  linkedTickets: number;
  unmappedItems: RoadmapItem[];
  mappedItems: RoadmapItem[];
  coverageRows: RoadmapItemCoverageRow[];
};

type RoadmapItemCoverageRow = {
  id: string;
  product: string;
  bucket: string;
  programAreas: string;
  roadmapItems: number;
  linkedTickets: number;
};

type RoadmapTicketAttribution = {
  ticketKey: string;
  mappingStatus: string;
  roadmapItemId: number | null;
  roadmapItemKey: string | null;
  roadmapItemTitle: string | null;
  products: string[];
  teamMembers: string[];
  buckets: string[];
  programAreas: string[];
  actualHours: number;
  actualCost: number;
  worklogCount: number;
  mappingCandidates: RoadmapItemCandidate[];
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
  const [roadmapForecastActualRows, setRoadmapForecastActualRows] = useState<RoadmapActualRow[]>([]);
  const [roadmapGaps, setRoadmapGaps] = useState<RoadmapActualRow[]>([]);
  const [reportedRows, setReportedRows] = useState<ReportedValueRow[]>([]);
  const [forecastDecisions, setForecastDecisions] = useState<ForecastRecommendationDecision[]>([]);
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [attributionChanges, setAttributionChanges] = useState<AttributionChange[]>([]);
  const [jiraStatus, setJiraStatus] = useState<JiraIntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [liveSyncing, setLiveSyncing] = useState(false);
  const [roadmapSyncing, setRoadmapSyncing] = useState(false);
  const [catalogRefreshing, setCatalogRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [roadmapFilters, setRoadmapFilters] = useState<RoadmapFilterState>(EMPTY_ROADMAP_FILTERS);
  const [forecastRecommendationTargets, setForecastRecommendationTargets] = useState<Record<string, ForecastRecommendationTarget>>({});
  const [submittingForecastDecision, setSubmittingForecastDecision] = useState<string | null>(null);

  async function loadData() {
    const monthSequence = roadmapFilters.monthSequence ? Number(roadmapFilters.monthSequence) : null;
    const [
      members,
      productRows,
      bucketRows,
      users,
      jiraProducts,
      catalogRows,
      roadmapRows,
      actualRows,
      forecastActualRows,
      gapRows,
      reportedValueRows,
      forecastDecisionRows,
      runs,
      changeRows,
      status,
    ] = await Promise.all([
      api.teamMembers(),
      api.products(),
      api.buckets(),
      api.userMappings(),
      api.productMappings(),
      api.jiraProjectCatalog(),
      api.roadmapItems(fiscalYear),
      api.roadmapActuals(fiscalYear, { monthSequence }),
      api.roadmapActuals(fiscalYear),
      api.roadmapActualGaps(fiscalYear, { monthSequence }),
      api.reportedValues({}, fiscalYear),
      api.forecastRecommendationDecisions(fiscalYear),
      api.syncRuns(),
      api.attributionChanges(),
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
    setRoadmapForecastActualRows(forecastActualRows);
    setRoadmapGaps(gapRows);
    setReportedRows(reportedValueRows);
    setForecastDecisions(forecastDecisionRows);
    setSyncRuns(runs);
    setAttributionChanges(changeRows);
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
      const result = await api.syncLiveJiraRovo(fiscalYear);
      await loadData();
      const syncedFiscalYear = result.fiscal_year ?? fiscalYear;
      const selectedYearNote =
        result.requested_fiscal_year && result.requested_fiscal_year !== syncedFiscalYear
          ? ` Selected view was FY${result.requested_fiscal_year}; live Jira Actuals stay on the current fiscal year.`
          : "";
      setNotice(
        `Jira actuals synced for FY${syncedFiscalYear} (${formatFiscalYearRangeLabel(syncedFiscalYear)}): ${result.imported_worklogs} worklogs imported, ${result.deleted_worklogs} stale worklogs removed, ${result.skipped_unmapped_worklogs} skipped for mapping.${selectedYearNote}`,
      );
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
      const result = await api.syncRoadmap(fiscalYear);
      await loadData();
      const removedCopy = result.removed_from_fiscal_year
        ? ` ${result.removed_from_fiscal_year} stale items moved out of ${result.fiscal_year_label ?? fiscalYearLabel}.`
        : "";
      setNotice(
        `Roadmap synced for ${result.fiscal_year_label ?? fiscalYearLabel}: ${result.roadmap_items} items and ${result.linked_issues} linked Jira work items.${removedCopy}`,
      );
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

  async function updateRoadmapItemMapping(
    item: RoadmapItem,
    updates: Partial<Pick<RoadmapItem, "product_id" | "bucket_id">>,
  ) {
    setError(null);
    setNotice(null);
    try {
      const updatedItem = await api.updateRoadmapItemMapping(item.id, updates);
      setRoadmapItems((current) => current.map((item) => (item.id === updatedItem.id ? updatedItem : item)));
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update Roadmap Item mapping");
    }
  }

  async function updateRoadmapTicketMapping(attribution: RoadmapTicketAttribution, roadmapItemId: number | null) {
    if (attribution.roadmapItemId === roadmapItemId && attribution.mappingStatus === "mapped") return;
    const targetItem = roadmapItems.find((item) => item.id === roadmapItemId);
    const fromLabel = attribution.roadmapItemId
      ? `${attribution.roadmapItemKey ?? "Roadmap Item"} - ${attribution.roadmapItemTitle ?? "Untitled"}`
      : attribution.mappingStatus;
    const toLabel = targetItem ? `${targetItem.jira_issue_key} - ${targetItem.title}` : "Unmapped";
    const confirmed = window.confirm(
      `Change ${attribution.ticketKey} from ${fromLabel} to ${toLabel}?\n\n` +
        `This changes ${fiscalYearLabel} Roadmap attribution for ${attribution.worklogCount} worklogs, ` +
        `${formatHours(attribution.actualHours)} hours, and ${formatCurrency(attribution.actualCost)}. Product ownership and Forecasts will not change.`,
    );
    if (!confirmed) return;
    setError(null);
    setNotice(null);
    try {
      await api.updateRoadmapTicketMapping(attribution.ticketKey, {
        roadmap_item_id: roadmapItemId,
        fiscal_year: fiscalYear,
        reason: "Manual Roadmap ticket attribution correction",
      });
      await loadData();
      setNotice(
        `${attribution.ticketKey} was assigned to ${toLabel} for ${fiscalYearLabel}. ` +
          `${formatHours(attribution.actualHours)} hours and ${formatCurrency(attribution.actualCost)} now roll up through that attribution.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update ticket Roadmap Item mapping");
    }
  }

  function updateForecastRecommendationTarget(rowId: string, updates: Partial<ForecastRecommendationTarget>) {
    setForecastRecommendationTargets((current) => {
      const existing = current[rowId] ?? { teamMemberId: "", monthSequence: "", note: "" };
      return {
        ...current,
        [rowId]: {
          ...existing,
          ...updates,
        },
      };
    });
  }

  async function recordForecastRecommendationDecision(row: RoadmapForecastComparisonRow, action: ForecastRecommendationAction) {
    setError(null);
    setNotice(null);
    const target = forecastRecommendationTargets[row.id] ?? { teamMemberId: "", monthSequence: "", note: "" };
    if (action === "applied" && (!target.teamMemberId || !target.monthSequence)) {
      setError("Choose a target Team Member and Fiscal Month before applying a forecast recommendation.");
      return;
    }
    const targetMember = teamMembers.find((member) => member.id === Number(target.teamMemberId));
    const confirmation =
      action === "applied"
        ? `Add ${formatHours(row.suggestedDeltaHours)} Forecast hours to ${targetMember?.name ?? "the selected Team Member"} in ${fiscalMonthLabel(fiscalYear, Number(target.monthSequence))} for ${row.product} / ${row.bucket}?\n\nFull-year Forecast will change from ${formatHours(row.forecastHours)} to ${formatHours(row.suggestedForecastHours)} hours. Mapped Roadmap Actual is ${formatHours(row.actualHours)} hours. Actual hours will not change.`
        : `Dismiss the current ${row.product} / ${row.bucket} recommendation?\n\nForecast and Actual hours will not change. The recommendation will return if its full-year Forecast or mapped Roadmap Actual total changes.`;
    if (!window.confirm(confirmation)) return;

    const submissionKey = `${row.id}:${action}`;
    setSubmittingForecastDecision(submissionKey);
    try {
      await api.createForecastRecommendationDecision({
        fiscal_year: fiscalYear,
        product_id: row.productId,
        bucket_id: row.bucketId,
        action,
        expected_forecast_hours: row.forecastHours,
        expected_roadmap_actual_hours: row.actualHours,
        target_team_member_id: action === "applied" ? Number(target.teamMemberId) : null,
        target_month_sequence: action === "applied" ? Number(target.monthSequence) : null,
        note: target.note.trim() || null,
      });
      await loadData();
      if (action === "applied") {
        setForecastRecommendationTargets((current) => ({
          ...current,
          [row.id]: { teamMemberId: "", monthSequence: "", note: "" },
        }));
      }
      setNotice(
        action === "applied"
          ? `${formatHours(row.suggestedDeltaHours)} Forecast hours added for ${row.product} / ${row.bucket}.`
          : `Current Forecast recommendation dismissed for ${row.product} / ${row.bucket}.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to record forecast recommendation decision");
    } finally {
      setSubmittingForecastDecision(null);
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

  function exportRoadmapForecastComparison() {
    downloadCsv(
      `sparc-roadmap-forecast-comparison-${fiscalYearLabel.toLowerCase()}.csv`,
      roadmapForecastComparisonCsvRows(roadmapForecastComparison),
    );
  }

  const catalogLastCheckedAt = useMemo(() => latestCatalogCheckedAt(jiraCatalog), [jiraCatalog]);
  const sortedRoadmapItems = useMemo(() => sortRoadmapItems(roadmapItems), [roadmapItems]);
  const roadmapItemMappingSummary = useMemo(() => buildRoadmapItemMappingSummary(roadmapItems), [roadmapItems]);
  const programAreaOptions = useMemo(() => programAreaOptionsFrom(roadmapActualRows, roadmapItems), [roadmapActualRows, roadmapItems]);
  const visibleRoadmapActualRows = useMemo(() => filterRoadmapActualRows(roadmapActualRows, roadmapFilters), [roadmapActualRows, roadmapFilters]);
  const visibleFullYearRoadmapActualRows = useMemo(
    () => filterRoadmapActualRows(roadmapForecastActualRows, roadmapFilters),
    [roadmapForecastActualRows, roadmapFilters],
  );
  const visibleRoadmapGapRows = useMemo(() => filterRoadmapActualRows(roadmapGaps, roadmapFilters), [roadmapGaps, roadmapFilters]);
  const visibleMappedRoadmapActualRows = useMemo(
    () => visibleRoadmapActualRows.filter((row) => row.mapping_status === "mapped"),
    [visibleRoadmapActualRows],
  );
  const visibleReportedRows = useMemo(() => filterReportedRows(reportedRows, roadmapFilters), [reportedRows, roadmapFilters]);
  const roadmapTicketAttributions = useMemo(() => {
    const fullYearAttributions = buildRoadmapTicketAttributions(visibleFullYearRoadmapActualRows);
    if (!roadmapFilters.monthSequence) return fullYearAttributions;
    const selectedMonthTickets = new Set(buildRoadmapTicketAttributions(visibleRoadmapActualRows).map((row) => row.ticketKey));
    return fullYearAttributions.filter((row) => selectedMonthTickets.has(row.ticketKey));
  }, [roadmapFilters.monthSequence, visibleFullYearRoadmapActualRows, visibleRoadmapActualRows]);
  const roadmapGapTickets = useMemo(
    () => roadmapTicketAttributions.filter((attribution) => attribution.mappingStatus !== "mapped"),
    [roadmapTicketAttributions],
  );
  const billingSummary = useMemo(
    () => buildRoadmapBillingSummary(visibleMappedRoadmapActualRows, visibleRoadmapGapRows),
    [visibleMappedRoadmapActualRows, visibleRoadmapGapRows],
  );
  const roadmapForecastComparison = useMemo(
    () => buildRoadmapForecastComparison(visibleMappedRoadmapActualRows, visibleReportedRows),
    [visibleMappedRoadmapActualRows, visibleReportedRows],
  );
  const forecastReviewQueue = useMemo(
    () => buildRoadmapForecastComparison(roadmapForecastActualRows.filter((row) => row.mapping_status === "mapped"), reportedRows),
    [roadmapForecastActualRows, reportedRows],
  );

  if (loading) return <LoadingBlock />;
  if (error && !jiraStatus) return <ErrorBlock message={error} />;

  const unmappedUserCount = userMappings.filter((mapping) => mapping.team_member_id === null).length;
  const unmappedProductCount = productMappings.filter((mapping) => mapping.product_id === null).length;
  const unmappedRoadmapCount = roadmapItemMappingSummary.needsMapping;

  return (
    <div className="space-y-5">
      <section className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end">
        <div>
          {embedded ? <h2 className="text-xl font-semibold">Jira Sync</h2> : <h1 className="text-2xl font-semibold">Jira Sync</h1>}
          <p className="mt-1 text-sm text-muted-foreground">
            Live Jira actual-hours sync is limited to the current fiscal year. Roadmap views follow {fiscalYearLabel} ({fiscalYearRangeLabel}).
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

      <RoadmapForecastComparisonSection
        rows={roadmapForecastComparison}
        programAreaFiltered={Boolean(roadmapFilters.programArea)}
        statusFiltered={Boolean(roadmapFilters.mappingStatus)}
        onExport={exportRoadmapForecastComparison}
      />

      <ForecastRecommendationReviewSection
        decisions={forecastDecisions}
        fiscalYear={fiscalYear}
        rows={forecastReviewQueue}
        submittingKey={submittingForecastDecision}
        targets={forecastRecommendationTargets}
        teamMembers={teamMembers}
        onDecision={recordForecastRecommendationDecision}
        onTargetChange={updateForecastRecommendationTarget}
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

      <MappingTable title="Discovered Jira Projects" unmapped={unmappedProductCount}>
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
                <TableCell>{mapping.product ?? "Unmapped - assign in Product Settings"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </MappingTable>

      <RoadmapItemMappingWorkbench
        buckets={buckets}
        products={products}
        summary={roadmapItemMappingSummary}
        onChange={updateRoadmapItemMapping}
      />

      <MappingTable title="Roadmap Ticket Attribution" unmapped={roadmapGapTickets.length} badgeLabel="gaps">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ticket</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Team Members</TableHead>
              <TableHead>Bucket</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>FY Impact</TableHead>
              <TableHead>Roadmap Item</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {roadmapTicketAttributions.length ? (
              roadmapTicketAttributions.map((attribution) => {
                const roadmapItemOptions = attribution.mappingStatus === "ambiguous" ? attribution.mappingCandidates : sortedRoadmapItems;
                const selectValue = attribution.mappingStatus === "mapped" && attribution.roadmapItemId ? String(attribution.roadmapItemId) : "";
                return (
                  <TableRow key={attribution.ticketKey}>
                    <TableCell>
                      <div className="font-medium text-primary">{attribution.ticketKey}</div>
                    </TableCell>
                    <TableCell>{attribution.products.join(", ")}</TableCell>
                    <TableCell>{attribution.teamMembers.join(", ")}</TableCell>
                    <TableCell>{attribution.buckets.join(", ")}</TableCell>
                    <TableCell>
                      <Badge
                        className={
                          attribution.mappingStatus === "mapped"
                            ? "border-primary/40 text-primary"
                            : attribution.mappingStatus === "ambiguous"
                              ? "border-warning/50 text-warning"
                              : "border-muted text-muted-foreground"
                        }
                      >
                        {attribution.mappingStatus}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div>{formatHours(attribution.actualHours)} / {formatCurrency(attribution.actualCost)}</div>
                      <div className="text-xs text-muted-foreground">{attribution.worklogCount} worklogs</div>
                    </TableCell>
                    <TableCell>
                      <select
                        className="h-9 w-full min-w-64 rounded-md border border-input bg-background px-2 text-sm"
                        value={selectValue}
                        onChange={(event) => void updateRoadmapTicketMapping(attribution, event.target.value ? Number(event.target.value) : null)}
                      >
                        <option value="">
                          {attribution.mappingStatus === "mapped"
                            ? "Leave unmapped"
                            : attribution.mappingStatus === "ambiguous"
                              ? "Choose competing Roadmap Item"
                              : "Map to Roadmap Item"}
                        </option>
                        {roadmapItemOptions.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.jira_issue_key} - {item.title}
                          </option>
                        ))}
                      </select>
                    </TableCell>
                  </TableRow>
                );
              })
            ) : (
              <TableRow>
                <TableCell className="py-6 text-sm text-muted-foreground" colSpan={7}>
                  No Jira Actual tickets for {fiscalYearLabel}.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </MappingTable>

      <Card>
        <CardHeader>
          <CardTitle>Recent Attribution Changes</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Correction</TableHead>
                <TableHead>Impact</TableHead>
                <TableHead>Changed By</TableHead>
                <TableHead>Changed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {attributionChanges.length ? (
                attributionChanges.map((change) => (
                  <TableRow key={change.id}>
                    <TableCell>
                      <div className="font-medium text-primary">{change.source_key}</div>
                      <div className="text-xs text-muted-foreground">{attributionChangeTypeLabel(change.change_type)}</div>
                    </TableCell>
                    <TableCell>
                      <div>{change.from_value ?? "Unmapped"} to {change.to_value ?? "Unmapped"}</div>
                      {change.reason ? <div className="text-xs text-muted-foreground">{change.reason}</div> : null}
                    </TableCell>
                    <TableCell>
                      <div>{formatHours(change.affected_hours)} / {formatCurrency(change.affected_cost)}</div>
                      <div className="text-xs text-muted-foreground">{change.affected_actual_count} Actual entries</div>
                    </TableCell>
                    <TableCell>{change.changed_by_display_name}</TableCell>
                    <TableCell>{formatDateTime(change.created_at)}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell className="py-6 text-sm text-muted-foreground" colSpan={5}>
                    No attribution corrections have been recorded.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sync History</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Status</TableHead>
                <TableHead>Sync</TableHead>
                <TableHead>Results</TableHead>
                <TableHead>Completed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {syncRuns.map((run) => {
                const result = syncRunResult(run);
                return (
                  <TableRow key={run.id}>
                    <TableCell className="align-top">
                      <Badge className={syncStatusClassName(run.status)}>
                        {syncStatusLabel(run.status)}
                      </Badge>
                      {run.error_summary ? <div className="mt-1 max-w-64 text-xs text-destructive">{run.error_summary}</div> : null}
                    </TableCell>
                    <TableCell className="align-top">
                      <div className="font-medium text-foreground">{result.sourceLabel}</div>
                      <div className="mt-0.5 text-xs text-muted-foreground">{result.sourceDetail}</div>
                    </TableCell>
                    <TableCell className="align-top">
                      <div className="font-medium text-foreground">{result.primaryResult}</div>
                      <div className="mt-1 text-sm text-muted-foreground">{result.secondaryResult}</div>
                      {result.secondaryDetail ? <div className="mt-0.5 text-xs text-muted-foreground">{result.secondaryDetail}</div> : null}
                    </TableCell>
                    <TableCell className="whitespace-nowrap align-top">
                      {run.completed_at ? formatSyncDateTime(run.completed_at) : "In progress"}
                    </TableCell>
                  </TableRow>
                );
              })}
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
        <SummaryMetric label="Mapped Hours" value={formatHours(summary.totals.actualHours)} />
        <SummaryMetric label="Mapped Cost" value={formatCurrency(summary.totals.actualCost)} />
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
                  No mapped roadmap actuals match the selected filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

function RoadmapForecastComparisonSection({
  rows,
  programAreaFiltered,
  statusFiltered,
  onExport,
}: {
  rows: RoadmapForecastComparisonRow[];
  programAreaFiltered: boolean;
  statusFiltered: boolean;
  onExport: () => void;
}) {
  const totals = rows.reduce(
    (current, row) => ({
      forecastHours: current.forecastHours + row.forecastHours,
      actualHours: current.actualHours + row.actualHours,
      actualCost: current.actualCost + row.actualCost,
      remainingHours: current.remainingHours + row.remainingHours,
      suggestedDeltaHours: current.suggestedDeltaHours + row.suggestedDeltaHours,
      tickets: current.tickets + row.tickets,
      gapTickets: current.gapTickets + row.gapTickets,
    }),
    { forecastHours: 0, actualHours: 0, actualCost: 0, remainingHours: 0, suggestedDeltaHours: 0, tickets: 0, gapTickets: 0 },
  );
  const totalPercentUsed = totals.forecastHours > 0 ? (totals.actualHours / totals.forecastHours) * 100 : null;

  return (
    <section className="space-y-3 rounded-lg border bg-card p-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
        <div>
          <h2 className="text-lg font-semibold">Roadmap Forecast Comparison</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Mapped roadmap actuals compared to Product/Bucket forecast hours. Gap tickets stay in the mapping queue until linked to Roadmap Ideas.
          </p>
        </div>
        <Button type="button" variant="outline" onClick={onExport}>
          <Download className="h-4 w-4" />
          Comparison CSV
        </Button>
      </div>
      {programAreaFiltered || statusFiltered ? (
        <div className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
          Forecast rows are not split by Roadmap Item status or Program Area yet, so those filters are reflected on the actuals side of this comparison.
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-7">
        <SummaryMetric label="Forecast Hrs" value={formatHours(totals.forecastHours)} />
        <SummaryMetric label="Roadmap Actual Hrs" value={formatHours(totals.actualHours)} />
        <SummaryMetric label="Remaining Hrs" value={formatSignedHours(totals.remainingHours)} tone={totals.remainingHours < 0 ? "warn" : "default"} />
        <SummaryMetric label="Suggested Add Hrs" value={formatHours(totals.suggestedDeltaHours)} tone={totals.suggestedDeltaHours > 0 ? "warn" : "default"} />
        <SummaryMetric label="Actual Cost" value={formatCurrency(totals.actualCost)} />
        <SummaryMetric label="% Used" value={formatPercent(totalPercentUsed)} tone={totalPercentUsed !== null && totalPercentUsed >= 100 ? "warn" : "default"} />
        <SummaryMetric label="Gap Tickets" value={String(totals.gapTickets)} tone={totals.gapTickets ? "warn" : "default"} />
      </div>
      <div className="overflow-hidden rounded-lg border">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>Bucket</TableHead>
                <TableHead>Program Areas</TableHead>
                <TableHead className="text-right">Roadmap Items</TableHead>
                <TableHead className="text-right">Tickets</TableHead>
                <TableHead className="text-right">Forecast Hrs</TableHead>
                <TableHead className="text-right">Actual Hrs</TableHead>
                <TableHead className="text-right">Remaining Hrs</TableHead>
                <TableHead className="text-right">Suggested Add</TableHead>
                <TableHead className="text-right">% Used</TableHead>
                <TableHead>Review</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length ? (
                rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">{row.product}</TableCell>
                    <TableCell>{row.bucket}</TableCell>
                    <TableCell>{row.programAreas}</TableCell>
                    <TableCell className="numeric-cell text-right">{row.roadmapItems}</TableCell>
                    <TableCell className="numeric-cell text-right">
                      {row.tickets}
                      {row.gapTickets ? <span className="ml-1 text-warning">({row.gapTickets} gaps)</span> : null}
                    </TableCell>
                    <TableCell className="numeric-cell text-right">{formatHours(row.forecastHours)}</TableCell>
                    <TableCell className="numeric-cell text-right font-semibold">{formatHours(row.actualHours)}</TableCell>
                    <TableCell className={`numeric-cell text-right font-semibold ${row.remainingHours < 0 ? "text-warning" : "text-primary"}`}>
                      {formatSignedHours(row.remainingHours)}
                    </TableCell>
                    <TableCell className={`numeric-cell text-right font-semibold ${row.suggestedDeltaHours > 0 ? "text-warning" : "text-muted-foreground"}`}>
                      {formatHours(row.suggestedDeltaHours)}
                    </TableCell>
                    <TableCell className="numeric-cell text-right">{formatPercent(row.percentUsed)}</TableCell>
                    <TableCell>
                      <RoadmapForecastRecommendationBadge recommendation={row.recommendation} />
                    </TableCell>
                    <TableCell>
                      <RoadmapForecastStatusBadge status={row.status} />
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell className="py-5 text-sm text-muted-foreground" colSpan={12}>
                    No roadmap actuals match the selected filters yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </section>
  );
}

function RoadmapForecastStatusBadge({ status }: { status: RoadmapForecastComparisonRow["status"] }) {
  const statusMap: Record<RoadmapForecastComparisonRow["status"], { label: string; className: string }> = {
    on_track: { label: "On track", className: "border-primary/40 text-primary" },
    near_forecast: { label: "Near forecast", className: "border-warning/50 text-warning" },
    over_forecast: { label: "Over forecast", className: "border-destructive/40 text-destructive" },
    no_forecast: { label: "No forecast", className: "border-destructive/40 text-destructive" },
    mapping_gaps: { label: "Mapping gaps", className: "border-warning/50 text-warning" },
  };
  const display = statusMap[status];
  return <Badge className={display.className}>{display.label}</Badge>;
}

function RoadmapForecastRecommendationBadge({ recommendation }: { recommendation: RoadmapForecastComparisonRow["recommendation"] }) {
  const recommendationMap: Record<RoadmapForecastComparisonRow["recommendation"], { label: string; className: string }> = {
    none: { label: "No change", className: "border-primary/40 text-primary" },
    monitor: { label: "Monitor", className: "border-warning/50 text-warning" },
    resolve_gaps: { label: "Resolve gaps", className: "border-warning/50 text-warning" },
    add_forecast: { label: "Add forecast", className: "border-destructive/40 text-destructive" },
    increase_forecast: { label: "Increase forecast", className: "border-destructive/40 text-destructive" },
  };
  const display = recommendationMap[recommendation];
  return <Badge className={display.className}>{display.label}</Badge>;
}

function ForecastRecommendationReviewSection({
  decisions,
  fiscalYear,
  rows,
  submittingKey,
  targets,
  teamMembers,
  onDecision,
  onTargetChange,
}: {
  decisions: ForecastRecommendationDecision[];
  fiscalYear: number;
  rows: RoadmapForecastComparisonRow[];
  submittingKey: string | null;
  targets: Record<string, ForecastRecommendationTarget>;
  teamMembers: TeamMember[];
  onDecision: (row: RoadmapForecastComparisonRow, action: ForecastRecommendationAction) => void;
  onTargetChange: (rowId: string, updates: Partial<ForecastRecommendationTarget>) => void;
}) {
  const allActionableRows = rows.filter(isActionableForecastRecommendation);
  const actionableRows = activeForecastRecommendationRows(rows, decisions);
  const dismissedRows = allActionableRows.length - actionableRows.length;
  const activeTeamMembers = teamMembers.filter((member) => member.status === "active");
  const totals = actionableRows.reduce(
    (current, row) => ({
      rows: current.rows + 1,
      actualHours: current.actualHours + row.actualHours,
      suggestedDeltaHours: current.suggestedDeltaHours + row.suggestedDeltaHours,
    }),
    { rows: 0, actualHours: 0, suggestedDeltaHours: 0 },
  );

  return (
    <section className="space-y-3 rounded-lg border bg-card p-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
        <div>
          <h2 className="text-lg font-semibold">Forecast Adjustment Review</h2>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Full-year Product and bucket comparisons from mapped Roadmap Actuals. Add the proposed hours to one Team Member and month, or dismiss the current recommendation without changing Forecast. Billing filters above do not change this full-year review.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:min-w-[24rem]">
          <SummaryMetric label="Pending" value={String(totals.rows)} />
          <SummaryMetric label="Mapped Actual Hrs" value={formatHours(totals.actualHours)} />
          <SummaryMetric label="Proposed Add" value={formatHours(totals.suggestedDeltaHours)} tone={totals.suggestedDeltaHours ? "warn" : "default"} />
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>Bucket</TableHead>
                <TableHead className="text-right">Current Forecast</TableHead>
                <TableHead className="text-right">Mapped Actual</TableHead>
                <TableHead className="text-right">Add to Forecast</TableHead>
                <TableHead>Forecast Owner</TableHead>
                <TableHead>Forecast Month</TableHead>
                <TableHead>Note</TableHead>
                <TableHead>Decision</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {actionableRows.length ? (
                actionableRows.map((row) => {
                  const target = targets[row.id] ?? { teamMemberId: "", monthSequence: "", note: "" };
                  const applyKey = `${row.id}:applied`;
                  const rejectKey = `${row.id}:rejected`;
                  return (
                    <TableRow key={row.id}>
                      <TableCell>
                        <div className="font-medium text-primary">{row.product}</div>
                        <div className="text-xs text-muted-foreground">{row.programAreas}</div>
                      </TableCell>
                      <TableCell>
                        <div>{row.bucket}</div>
                        <RoadmapForecastRecommendationBadge recommendation={row.recommendation} />
                      </TableCell>
                      <TableCell className="numeric-cell text-right">{formatHours(row.forecastHours)}</TableCell>
                      <TableCell className="numeric-cell text-right font-semibold">{formatHours(row.actualHours)}</TableCell>
                      <TableCell className="numeric-cell text-right font-semibold text-warning">{formatHours(row.suggestedDeltaHours)}</TableCell>
                      <TableCell>
                        <select
                          aria-label={`Forecast owner for ${row.product} ${row.bucket}`}
                          className="h-9 w-full min-w-52 rounded-md border border-input bg-background px-2 text-sm"
                          value={target.teamMemberId}
                          onChange={(event) => onTargetChange(row.id, { teamMemberId: event.target.value })}
                        >
                          <option value="">Select Team Member</option>
                          {activeTeamMembers.map((member) => (
                            <option key={member.id} value={member.id}>
                              {member.name} - {member.role}
                            </option>
                          ))}
                        </select>
                      </TableCell>
                      <TableCell>
                        <select
                          aria-label={`Forecast month for ${row.product} ${row.bucket}`}
                          className="h-9 w-full min-w-36 rounded-md border border-input bg-background px-2 text-sm"
                          value={target.monthSequence}
                          onChange={(event) => onTargetChange(row.id, { monthSequence: event.target.value })}
                        >
                          <option value="">Select Month</option>
                          {fiscalMonthOptions(fiscalYear).map((month) => (
                            <option key={month.sequence} value={month.sequence}>
                              {month.label}
                            </option>
                          ))}
                        </select>
                      </TableCell>
                      <TableCell>
                        <textarea
                          aria-label={`Decision note for ${row.product} ${row.bucket}`}
                          className="min-h-9 w-full min-w-56 resize-y rounded-md border border-input bg-background px-2 py-1 text-sm"
                          value={target.note}
                          onChange={(event) => onTargetChange(row.id, { note: event.target.value })}
                          placeholder="Optional decision note"
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-2">
                          <Button
                            disabled={submittingKey !== null || !target.teamMemberId || !target.monthSequence}
                            size="sm"
                            type="button"
                            onClick={() => onDecision(row, "applied")}
                          >
                            <CheckCircle2 className="h-4 w-4" />
                            {submittingKey === applyKey ? "Adding" : "Add Hours"}
                          </Button>
                          <Button
                            disabled={submittingKey !== null}
                            size="sm"
                            type="button"
                            variant="outline"
                            onClick={() => onDecision(row, "rejected")}
                          >
                            <XCircle className="h-4 w-4" />
                            {submittingKey === rejectKey ? "Dismissing" : "Dismiss"}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              ) : (
                <TableRow>
                  <TableCell className="py-5 text-sm text-muted-foreground" colSpan={9}>
                    No pending Forecast adjustments for this fiscal year.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>
      {dismissedRows ? (
        <div className="text-sm text-muted-foreground">
          {dismissedRows} current {dismissedRows === 1 ? "recommendation is" : "recommendations are"} dismissed and recorded below. A dismissed recommendation returns if its full-year totals change.
        </div>
      ) : null}
      <ForecastRecommendationDecisionHistory decisions={decisions} fiscalYear={fiscalYear} />
    </section>
  );
}

function ForecastRecommendationDecisionHistory({
  decisions,
  fiscalYear,
}: {
  decisions: ForecastRecommendationDecision[];
  fiscalYear: number;
}) {
  return (
    <section className="overflow-hidden rounded-lg border">
      <div className="border-b bg-secondary/50 px-3 py-2 text-sm font-semibold">Recent Decisions</div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Decision</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Bucket</TableHead>
              <TableHead className="text-right">Decision Snapshot</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>Note</TableHead>
              <TableHead>Decided</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {decisions.length ? (
              decisions.slice(0, 8).map((decision) => (
                <TableRow key={decision.id}>
                  <TableCell>
                    <ForecastDecisionActionBadge action={decision.action} />
                  </TableCell>
                  <TableCell className="font-medium">{decision.product ?? "Unknown product"}</TableCell>
                  <TableCell>{decision.bucket ?? "Unknown bucket"}</TableCell>
                  <TableCell className="numeric-cell text-right">
                    <div>{formatHours(decision.roadmap_actual_hours)} mapped actual</div>
                    <div className="text-xs text-muted-foreground">{formatHours(decision.forecast_hours)} prior forecast</div>
                    <div className="text-xs text-warning">+{formatHours(decision.suggested_delta_hours)} proposed</div>
                  </TableCell>
                  <TableCell>
                    {decision.action === "applied" ? (
                      <>
                        <div>
                          {decision.target_team_member_id ? (
                            <TeamMemberNameLink className="font-medium text-primary hover:underline" member={{ team_member_id: decision.target_team_member_id }}>
                              {decision.target_team_member ?? "Unknown Team Member"}
                            </TeamMemberNameLink>
                          ) : (
                            (decision.target_team_member ?? "Unknown Team Member")
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {decision.target_month_sequence ? fiscalMonthLabel(fiscalYear, decision.target_month_sequence) : "No month"}
                        </div>
                      </>
                    ) : (
                      <span className="text-muted-foreground">No Forecast change</span>
                    )}
                  </TableCell>
                  <TableCell className="max-w-72 truncate" title={decision.note ?? ""}>
                    {decision.note ?? ""}
                  </TableCell>
                  <TableCell>{formatDateTime(decision.decided_at)}</TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell className="py-5 text-sm text-muted-foreground" colSpan={7}>
                  No forecast recommendation decisions recorded yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

function ForecastDecisionActionBadge({ action }: { action: ForecastRecommendationAction }) {
  return action === "applied" ? (
    <Badge className="border-primary/40 text-primary">Forecast added</Badge>
  ) : (
    <Badge className="border-muted text-muted-foreground">Dismissed</Badge>
  );
}

function isActionableForecastRecommendation(row: RoadmapForecastComparisonRow) {
  return row.suggestedDeltaHours > 0 && (row.recommendation === "add_forecast" || row.recommendation === "increase_forecast");
}

function activeForecastRecommendationRows(
  rows: RoadmapForecastComparisonRow[],
  decisions: ForecastRecommendationDecision[],
) {
  return rows.filter((row) => {
    if (!isActionableForecastRecommendation(row)) return false;
    const latestDecision = decisions.find(
      (decision) => decision.product_id === row.productId && decision.bucket_id === row.bucketId,
    );
    return !(
      latestDecision?.action === "rejected" &&
      latestDecision.recommendation === row.recommendation &&
      hoursMatch(latestDecision.forecast_hours, row.forecastHours) &&
      hoursMatch(latestDecision.roadmap_actual_hours, row.actualHours) &&
      hoursMatch(latestDecision.suggested_delta_hours, row.suggestedDeltaHours)
    );
  });
}

function hoursMatch(left: number, right: number) {
  return Math.abs(left - right) < 0.005;
}

function RoadmapItemMappingWorkbench({
  buckets,
  products,
  summary,
  onChange,
}: {
  buckets: Bucket[];
  products: Product[];
  summary: RoadmapItemMappingSummary;
  onChange: (
    item: RoadmapItem,
    updates: Partial<Pick<RoadmapItem, "product_id" | "bucket_id">>,
  ) => void;
}) {
  return (
    <section className="space-y-3 rounded-lg border bg-card p-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
        <div>
          <h2 className="text-lg font-semibold">Roadmap Item Mapping</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Map unmapped Roadmap Items to Product and Bucket, then review mapped coverage by Product/Bucket for billing attribution.
          </p>
        </div>
        <Badge className={summary.needsMapping ? "border-destructive/40 text-destructive" : "border-primary/40 text-primary"}>
          {summary.needsMapping} need mapping
        </Badge>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <SummaryMetric label="Roadmap Items" value={String(summary.total)} />
        <SummaryMetric label="Mapped" value={String(summary.mapped)} />
        <SummaryMetric label="Need Mapping" value={String(summary.needsMapping)} tone={summary.needsMapping ? "warn" : "default"} />
        <SummaryMetric label="Need Product" value={String(summary.needsProduct)} tone={summary.needsProduct ? "warn" : "default"} />
        <SummaryMetric label="Need Bucket" value={String(summary.needsBucket)} tone={summary.needsBucket ? "warn" : "default"} />
        <SummaryMetric label="Linked Tickets" value={String(summary.linkedTickets)} />
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <RoadmapItemMappingTable
          buckets={buckets}
          emptyMessage="All Roadmap Items have Product and Bucket mappings."
          items={summary.unmappedItems}
          products={products}
          title="Needs Mapping"
          onChange={onChange}
        />
        <RoadmapItemCoverageTable rows={summary.coverageRows} />
      </div>
      <RoadmapItemMappingTable
        buckets={buckets}
        emptyMessage="No mapped Roadmap Items yet."
        items={summary.mappedItems}
        products={products}
        title="Mapped Roadmap Items"
        onChange={onChange}
      />
    </section>
  );
}

function RoadmapItemMappingTable({
  buckets,
  emptyMessage,
  items,
  products,
  title,
  onChange,
}: {
  buckets: Bucket[];
  emptyMessage: string;
  items: RoadmapItem[];
  products: Product[];
  title: string;
  onChange: (
    item: RoadmapItem,
    updates: Partial<Pick<RoadmapItem, "product_id" | "bucket_id">>,
  ) => void;
}) {
  return (
    <section className="overflow-hidden rounded-lg border">
      <div className="border-b bg-secondary/50 px-3 py-2 text-sm font-semibold">{title}</div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Roadmap Item</TableHead>
              <TableHead>Mapping</TableHead>
              <TableHead>Jira Category</TableHead>
              <TableHead className="text-right">Tickets</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Bucket</TableHead>
              <TableHead>Jira Agency Office</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length ? (
              items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <RoadmapItemIdentity item={item} />
                  </TableCell>
                  <TableCell>
                    <RoadmapItemMappingBadge item={item} />
                  </TableCell>
                  <TableCell>{item.source_category || "Not set"}</TableCell>
                  <TableCell className="numeric-cell text-right">{item.linked_issue_count}</TableCell>
                  <TableCell>
                    <select
                      className="h-9 w-full min-w-52 rounded-md border border-input bg-background px-2 text-sm"
                      value={item.product_id ?? ""}
                      onChange={(event) => onChange(item, { product_id: event.target.value ? Number(event.target.value) : null })}
                    >
                      <option value="">Use Jira links / unmapped</option>
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
                      onChange={(event) => onChange(item, { bucket_id: event.target.value ? Number(event.target.value) : null })}
                    >
                      <option value="">Use Jira category / unmapped</option>
                      {buckets.map((bucket) => (
                        <option key={bucket.id} value={bucket.id}>
                          {bucket.name}
                        </option>
                      ))}
                    </select>
                  </TableCell>
                  <TableCell>{item.program_area ?? "Not set in Jira"}</TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell className="py-5 text-sm text-muted-foreground" colSpan={7}>
                  {emptyMessage}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

function RoadmapItemCoverageTable({ rows }: { rows: RoadmapItemCoverageRow[] }) {
  return (
    <section className="overflow-hidden rounded-lg border">
      <div className="border-b bg-secondary/50 px-3 py-2 text-sm font-semibold">Mapped Coverage</div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Product</TableHead>
              <TableHead>Bucket</TableHead>
              <TableHead>Jira Agency Offices</TableHead>
              <TableHead className="text-right">Items</TableHead>
              <TableHead className="text-right">Tickets</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length ? (
              rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-medium">{row.product}</TableCell>
                  <TableCell>{row.bucket}</TableCell>
                  <TableCell>{row.programAreas}</TableCell>
                  <TableCell className="numeric-cell text-right">{row.roadmapItems}</TableCell>
                  <TableCell className="numeric-cell text-right">{row.linkedTickets}</TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell className="py-5 text-sm text-muted-foreground" colSpan={5}>
                  No mapped coverage yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

function RoadmapItemIdentity({ item }: { item: RoadmapItem }) {
  return (
    <div>
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
      <div className="text-xs text-muted-foreground">{item.status ?? "No status"}</div>
    </div>
  );
}

function RoadmapItemMappingBadge({ item }: { item: RoadmapItem }) {
  const missingProduct = item.product_id === null;
  const missingBucket = item.bucket_id === null;
  if (!missingProduct && !missingBucket) return <Badge className="border-primary/40 text-primary">mapped</Badge>;
  if (missingProduct && missingBucket) return <Badge className="border-destructive/40 text-destructive">needs product + bucket</Badge>;
  if (missingProduct) return <Badge className="border-warning/50 text-warning">needs product</Badge>;
  return <Badge className="border-warning/50 text-warning">needs bucket</Badge>;
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

function buildRoadmapItemMappingSummary(items: RoadmapItem[]): RoadmapItemMappingSummary {
  const sortedItems = sortRoadmapItems(items);
  const unmappedItems = sortedItems.filter((item) => item.product_id === null || item.bucket_id === null);
  const mappedItems = sortedItems.filter((item) => item.product_id !== null && item.bucket_id !== null);
  return {
    total: items.length,
    mapped: mappedItems.length,
    needsMapping: unmappedItems.length,
    needsProduct: items.filter((item) => item.product_id === null).length,
    needsBucket: items.filter((item) => item.bucket_id === null).length,
    linkedTickets: items.reduce((total, item) => total + item.linked_issue_count, 0),
    unmappedItems,
    mappedItems,
    coverageRows: buildRoadmapItemCoverageRows(mappedItems),
  };
}

function buildRoadmapItemCoverageRows(items: RoadmapItem[]) {
  const coverage = new Map<string, RoadmapItemCoverageAccumulator>();
  items.forEach((item) => {
    if (item.product_id === null || item.bucket_id === null) return;
    const key = `${item.product_id}:${item.bucket_id}`;
    const existing = coverage.get(key);
    const row =
      existing ??
      ({
        id: key,
        product: item.product ?? "Unmapped product",
        bucket: item.bucket ?? "Unmapped bucket",
        programAreas: new Set<string>(),
        roadmapItems: 0,
        linkedTickets: 0,
      } satisfies RoadmapItemCoverageAccumulator);
    row.roadmapItems += 1;
    row.linkedTickets += item.linked_issue_count;
    row.programAreas.add(item.program_area || "Unassigned");
    coverage.set(key, row);
  });

  return Array.from(coverage.values())
    .map((row) => ({
      id: row.id,
      product: row.product,
      bucket: row.bucket,
      programAreas: displaySet(row.programAreas, "program areas"),
      roadmapItems: row.roadmapItems,
      linkedTickets: row.linkedTickets,
    }))
    .sort((left, right) => right.roadmapItems - left.roadmapItems || left.product.localeCompare(right.product));
}

type RoadmapItemCoverageAccumulator = {
  id: string;
  product: string;
  bucket: string;
  programAreas: Set<string>;
  roadmapItems: number;
  linkedTickets: number;
};

function buildRoadmapTicketAttributions(rows: RoadmapActualRow[]): RoadmapTicketAttribution[] {
  const tickets = new Map<
    string,
    Omit<RoadmapTicketAttribution, "products" | "teamMembers" | "buckets" | "programAreas" | "mappingCandidates"> & {
      products: Set<string>;
      teamMembers: Set<string>;
      buckets: Set<string>;
      programAreas: Set<string>;
      mappingCandidates: Map<number, RoadmapItemCandidate>;
    }
  >();

  rows.forEach((row) => {
    row.ticket_attributions.forEach((detail) => {
      const current = tickets.get(detail.ticket_key) ?? {
        ticketKey: detail.ticket_key,
        mappingStatus: row.mapping_status,
        roadmapItemId: row.roadmap_item_id,
        roadmapItemKey: row.roadmap_item_key,
        roadmapItemTitle: row.roadmap_item_title,
        products: new Set<string>(),
        teamMembers: new Set<string>(),
        buckets: new Set<string>(),
        programAreas: new Set<string>(),
        actualHours: 0,
        actualCost: 0,
        worklogCount: 0,
        mappingCandidates: new Map<number, RoadmapItemCandidate>(),
      };
      current.products.add(row.product);
      current.teamMembers.add(row.team_member);
      current.buckets.add(row.bucket);
      current.programAreas.add(row.program_area || "Unassigned");
      current.actualHours += detail.actual_hours;
      current.actualCost += detail.actual_cost;
      current.worklogCount += detail.worklog_count;
      detail.mapping_candidates.forEach((candidate) => current.mappingCandidates.set(candidate.id, candidate));
      tickets.set(detail.ticket_key, current);
    });
  });

  return Array.from(tickets.values())
    .map((ticket) => ({
      ...ticket,
      products: Array.from(ticket.products).sort(),
      teamMembers: Array.from(ticket.teamMembers).sort(),
      buckets: Array.from(ticket.buckets).sort(),
      programAreas: Array.from(ticket.programAreas).sort(),
      mappingCandidates: Array.from(ticket.mappingCandidates.values()).sort((left, right) =>
        left.jira_issue_key.localeCompare(right.jira_issue_key),
      ),
    }))
    .sort(
      (left, right) =>
        roadmapAttributionStatusRank(left.mappingStatus) - roadmapAttributionStatusRank(right.mappingStatus) ||
        left.ticketKey.localeCompare(right.ticketKey),
    );
}

function roadmapAttributionStatusRank(status: string) {
  if (status === "ambiguous") return 0;
  if (status === "unmapped") return 1;
  return 2;
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

function filterReportedRows(rows: ReportedValueRow[], filters: RoadmapFilterState) {
  return rows.filter((row) => {
    if (filters.productId && row.product_id !== Number(filters.productId)) return false;
    if (filters.teamMemberId && row.team_member_id !== Number(filters.teamMemberId)) return false;
    if (filters.bucketId && row.bucket_id !== Number(filters.bucketId)) return false;
    if (filters.monthSequence && row.month_sequence !== Number(filters.monthSequence)) return false;
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

function fiscalMonthLabel(fiscalYear: number, sequence: number) {
  return fiscalMonthOptions(fiscalYear).find((month) => month.sequence === sequence)?.label ?? `Month ${sequence}`;
}

function buildRoadmapForecastComparison(actualRows: RoadmapActualRow[], reportedRows: ReportedValueRow[]): RoadmapForecastComparisonRow[] {
  const forecastHoursByProductBucket = new Map<string, number>();
  reportedRows.forEach((row) => {
    const key = productBucketKey(row.product_id, row.bucket_id);
    forecastHoursByProductBucket.set(key, (forecastHoursByProductBucket.get(key) ?? 0) + row.forecast_hours);
  });

  const rowsByProductBucket = new Map<string, RoadmapForecastComparisonAccumulator>();
  actualRows.forEach((row) => {
    const key = productBucketKey(row.product_id, row.bucket_id);
    const accumulator = ensureForecastComparisonAccumulator(rowsByProductBucket, key, row);
    accumulator.programAreas.add(row.program_area || "Unassigned");
    accumulator.teamMembers.add(row.team_member);
    accumulator.worklogs += row.worklog_count;
    accumulator.actualHours += row.actual_hours;
    accumulator.actualCost += row.actual_cost;
    if (row.roadmap_item_id !== null) {
      accumulator.roadmapItems.add(String(row.roadmap_item_id));
    }
    row.ticket_keys.forEach((ticketKey) => {
      accumulator.tickets.add(ticketKey);
      if (row.mapping_status !== "mapped") accumulator.gapTickets.add(ticketKey);
    });
  });

  return Array.from(rowsByProductBucket.values())
    .map((row) => {
      const forecastHours = forecastHoursByProductBucket.get(row.id) ?? 0;
      const remainingHours = forecastHours - row.actualHours;
      const percentUsed = forecastHours > 0 ? (row.actualHours / forecastHours) * 100 : null;
      const suggestedDeltaHours = Math.max(row.actualHours - forecastHours, 0);
      const status = forecastComparisonStatus(forecastHours, row.actualHours, row.gapTickets.size);
      return {
        id: row.id,
        productId: row.productId,
        bucketId: row.bucketId,
        product: row.product,
        bucket: row.bucket,
        programAreas: displaySet(row.programAreas, "program areas"),
        roadmapItems: row.roadmapItems.size,
        teamMembers: row.teamMembers.size,
        tickets: row.tickets.size,
        gapTickets: row.gapTickets.size,
        worklogs: row.worklogs,
        forecastHours,
        actualHours: row.actualHours,
        actualCost: row.actualCost,
        remainingHours,
        percentUsed,
        suggestedDeltaHours,
        suggestedForecastHours: forecastHours + suggestedDeltaHours,
        recommendation: forecastRecommendation(status),
        status,
      };
    })
    .sort((left, right) => {
      const leftRisk = forecastComparisonRiskRank(left.status);
      const rightRisk = forecastComparisonRiskRank(right.status);
      return leftRisk - rightRisk || right.actualHours - left.actualHours || left.product.localeCompare(right.product);
    });
}

function forecastRecommendation(status: RoadmapForecastComparisonRow["status"]): RoadmapForecastComparisonRow["recommendation"] {
  switch (status) {
    case "no_forecast":
      return "add_forecast";
    case "over_forecast":
      return "increase_forecast";
    case "mapping_gaps":
      return "resolve_gaps";
    case "near_forecast":
      return "monitor";
    case "on_track":
      return "none";
  }
}

type RoadmapForecastComparisonAccumulator = {
  id: string;
  productId: number;
  bucketId: number;
  product: string;
  bucket: string;
  programAreas: Set<string>;
  roadmapItems: Set<string>;
  teamMembers: Set<string>;
  tickets: Set<string>;
  gapTickets: Set<string>;
  worklogs: number;
  actualHours: number;
  actualCost: number;
};

function ensureForecastComparisonAccumulator(map: Map<string, RoadmapForecastComparisonAccumulator>, id: string, row: RoadmapActualRow) {
  const existing = map.get(id);
  if (existing) return existing;
  const created: RoadmapForecastComparisonAccumulator = {
    id,
    productId: row.product_id,
    bucketId: row.bucket_id,
    product: row.product,
    bucket: row.bucket,
    programAreas: new Set(),
    roadmapItems: new Set(),
    teamMembers: new Set(),
    tickets: new Set(),
    gapTickets: new Set(),
    worklogs: 0,
    actualHours: 0,
    actualCost: 0,
  };
  map.set(id, created);
  return created;
}

function productBucketKey(productId: number, bucketId: number) {
  return `${productId}:${bucketId}`;
}

function forecastComparisonStatus(
  forecastHours: number,
  actualHours: number,
  gapTickets: number,
): RoadmapForecastComparisonRow["status"] {
  if (forecastHours <= 0 && actualHours > 0) return "no_forecast";
  if (forecastHours > 0 && actualHours > forecastHours) return "over_forecast";
  if (gapTickets > 0) return "mapping_gaps";
  if (forecastHours > 0 && actualHours / forecastHours >= 0.85) return "near_forecast";
  return "on_track";
}

function forecastComparisonRiskRank(status: RoadmapForecastComparisonRow["status"]) {
  switch (status) {
    case "no_forecast":
      return 0;
    case "over_forecast":
      return 1;
    case "mapping_gaps":
      return 2;
    case "near_forecast":
      return 3;
    case "on_track":
      return 4;
  }
}

function buildRoadmapBillingSummary(rows: RoadmapActualRow[], gapRows: RoadmapActualRow[] = []): RoadmapBillingSummary {
  const programAreas = new Map<string, BillingSummaryAccumulator>();
  const products = new Map<string, BillingSummaryAccumulator>();
  const roadmapItems = new Map<string, BillingSummaryAccumulator>();
  const totals = newAccumulator("totals", "Totals");
  const gapTickets = new Set<string>();

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
  gapRows.forEach((row) => row.ticket_keys.forEach((ticketKey) => gapTickets.add(ticketKey)));

  return {
    totals: {
      actualHours: totals.actualHours,
      actualCost: totals.actualCost,
      tickets: totals.tickets.size,
      worklogs: totals.worklogs,
      gapTickets: gapTickets.size,
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

function roadmapGapCsvRows(gaps: RoadmapTicketAttribution[]) {
  return [
    ["ticket_key", "mapping_status", "products", "team_members", "buckets", "program_areas", "worklogs", "actual_hours", "actual_cost"],
    ...gaps.map((gap) => [
      gap.ticketKey,
      gap.mappingStatus,
      gap.products.join("; "),
      gap.teamMembers.join("; "),
      gap.buckets.join("; "),
      gap.programAreas.join("; "),
      gap.worklogCount,
      roundCsvNumber(gap.actualHours),
      roundCsvNumber(gap.actualCost),
    ]),
  ];
}

function roadmapForecastComparisonCsvRows(rows: RoadmapForecastComparisonRow[]) {
  return [
    [
      "product",
      "bucket",
      "program_areas",
      "roadmap_items",
      "team_members",
      "tickets",
      "gap_tickets",
      "worklogs",
      "forecast_hours",
      "roadmap_actual_hours",
      "roadmap_actual_cost",
      "remaining_hours",
      "suggested_add_hours",
      "suggested_forecast_hours",
      "percent_used",
      "recommendation",
      "status",
    ],
    ...rows.map((row) => [
      row.product,
      row.bucket,
      row.programAreas,
      row.roadmapItems,
      row.teamMembers,
      row.tickets,
      row.gapTickets,
      row.worklogs,
      roundCsvNumber(row.forecastHours),
      roundCsvNumber(row.actualHours),
      roundCsvNumber(row.actualCost),
      roundCsvNumber(row.remainingHours),
      roundCsvNumber(row.suggestedDeltaHours),
      roundCsvNumber(row.suggestedForecastHours),
      row.percentUsed === null ? "" : roundCsvNumber(row.percentUsed),
      row.recommendation,
      row.status,
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

function formatSignedHours(value: number) {
  if (value === 0) return formatHours(0);
  return value > 0 ? formatHours(value) : `-${formatHours(Math.abs(value))}`;
}

function formatPercent(value: number | null) {
  if (value === null) return "No forecast";
  return `${Math.round(value)}%`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function formatSyncDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function syncRunResult(run: SyncRun) {
  const imported = formatRecordCount(run.imported_count);
  const skipped = formatRecordCount(run.skipped_count);
  if (run.source === "jira" || run.source === "mock_jira_rovo") {
    return {
      sourceLabel: run.source === "jira" ? "Jira Actuals" : "Mock Jira Actuals",
      sourceDetail: run.source === "jira" ? "Live worklog sync" : "Test worklog sync",
      primaryResult: `${imported} ${run.imported_count === 1 ? "worklog" : "worklogs"} accepted`,
      secondaryResult: `${skipped} ${run.skipped_count === 1 ? "worklog" : "worklogs"} excluded`,
      secondaryDetail:
        run.skipped_count > 0
          ? "Missing Team Member, Product, or Work Type mapping"
          : "No mapping or Work Type exclusions",
    };
  }
  if (run.source === "jira_roadmap") {
    return {
      sourceLabel: "Jira Roadmap",
      sourceDetail: "Roadmap Item sync",
      primaryResult: `${imported} Roadmap ${run.imported_count === 1 ? "Item" : "Items"} synchronized`,
      secondaryResult:
        run.status === "completed"
          ? `${skipped} stale ${run.skipped_count === 1 ? "item" : "items"} removed from the Fiscal Year`
          : `${skipped} linked ${run.skipped_count === 1 ? "issue" : "issues"} processed before failure`,
      secondaryDetail: run.status === "completed" && run.skipped_count === 0 ? "No stale Roadmap Items removed" : null,
    };
  }
  return {
    sourceLabel: humanizeSyncSource(run.source),
    sourceDetail: run.mode === "live" ? "Live sync" : `${syncStatusLabel(run.mode)} sync`,
    primaryResult: `${imported} ${run.imported_count === 1 ? "record" : "records"} processed`,
    secondaryResult: `${skipped} ${run.skipped_count === 1 ? "record" : "records"} not applied`,
    secondaryDetail: null,
  };
}

function syncStatusLabel(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function syncStatusClassName(status: string) {
  if (status === "completed") return "border-primary/40 text-primary";
  if (status === "failed") return "border-destructive/40 text-destructive";
  return "border-warning/50 text-warning";
}

function humanizeSyncSource(value: string) {
  return syncStatusLabel(value.replace(/-/g, "_"));
}

function formatRecordCount(value: number) {
  return new Intl.NumberFormat().format(value);
}

function attributionChangeTypeLabel(changeType: string) {
  return changeType === "jira_project_product" ? "Jira project to Product" : "Jira ticket to Roadmap Item";
}

function latestCatalogCheckedAt(projects: JiraProjectCatalog[]) {
  const timestamps = projects.map((project) => Date.parse(project.last_checked_at)).filter(Number.isFinite);
  if (!timestamps.length) return null;
  return new Date(Math.max(...timestamps)).toISOString();
}
