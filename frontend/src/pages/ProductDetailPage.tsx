import { ChevronDown, ChevronRight, Plus, Trash2, UserPlus } from "lucide-react";
import { Fragment, useEffect, useId, useMemo, useState } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Link, useNavigate, useParams } from "react-router-dom";

import { BudgetTracker } from "../components/BudgetTracker";
import { PageNav } from "../components/PageNav";
import { ReportedValuesTable } from "../components/ReportedValuesTable";
import { RoadmapActualsTable } from "../components/RoadmapActualsTable";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import { productDetailPath, teamMemberDetailPath } from "../lib/routes";
import { formatCurrency, formatHours } from "../lib/utils";
import type {
  BucketTable,
  BucketTableRow,
  MonthCell,
  ProductBucketTables,
  ProductJiraSpace,
  ProductSummary,
  ProductTeamMember,
  ReportedValueRow,
  RoadmapActualRow,
  RoadmapItem,
  TeamMember,
} from "../types/api";

const PIE_COLORS = ["#2CCCD3", "#D2D755", "#E87722", "#5E7975"];
const COST_VARIANCE_HELP =
  "Actual cost minus forecast cost. Negative means actuals are under forecast; positive means actuals exceeded forecast.";

interface ProductRoleCostRow {
  role: string;
  memberCount: number;
  forecastCost: number;
}

interface ProductRoleCostSummary {
  rows: ProductRoleCostRow[];
  totalMembers: number;
  totalCost: number;
}

export function ProductDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const productRef = params.productRef ?? "";
  const { fiscalYear, fiscalYearLabel } = useFiscalYear();
  const [summary, setSummary] = useState<ProductSummary | null>(null);
  const [tables, setTables] = useState<ProductBucketTables | null>(null);
  const [productSpaces, setProductSpaces] = useState<ProductJiraSpace[]>([]);
  const [productTeam, setProductTeam] = useState<ProductTeamMember[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [reportedRows, setReportedRows] = useState<ReportedValueRow[]>([]);
  const [roadmapActualRows, setRoadmapActualRows] = useState<RoadmapActualRow[]>([]);
  const [roadmapItems, setRoadmapItems] = useState<RoadmapItem[]>([]);
  const [distribution, setDistribution] = useState<{ bucket: string; hours: number }[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [forecastLineMemberId, setForecastLineMemberId] = useState("");
  const [forecastLineBucketId, setForecastLineBucketId] = useState("");
  const [forecastLineSaving, setForecastLineSaving] = useState(false);
  const [forecastLineMessage, setForecastLineMessage] = useState<string | null>(null);
  const [savingCells, setSavingCells] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const productId = summary?.product.id ?? null;

  async function loadData() {
    const summaryResult = await api.productSummary(productRef, fiscalYear);
    const resolvedProductId = summaryResult.product.id;
    const [
      distributionResult,
      tablesResult,
      productSpacesResult,
      productTeamResult,
      teamMembersResult,
      reportedRowsResult,
      roadmapItemsResult,
      roadmapActualsResult,
    ] = await Promise.all([
      api.bucketDistribution(resolvedProductId, fiscalYear),
      api.productBucketTables(resolvedProductId, fiscalYear),
      api.productJiraSpaces(resolvedProductId),
      api.productTeamMembers(resolvedProductId),
      api.teamMembers(),
      api.reportedValues({ product_id: resolvedProductId }, fiscalYear),
      api.productRoadmapItems(resolvedProductId, fiscalYear),
      api.productRoadmapActuals(resolvedProductId, fiscalYear),
    ]);
    if (productRef !== summaryResult.product.slug) {
      navigate(productDetailPath(summaryResult.product), { replace: true });
    }
    setSummary(summaryResult);
    setDistribution(distributionResult.map((row) => ({ bucket: row.bucket, hours: row.hours })));
    setTables(tablesResult);
    setProductSpaces(productSpacesResult);
    setProductTeam(productTeamResult);
    setTeamMembers(teamMembersResult);
    setReportedRows(reportedRowsResult);
    setRoadmapItems(roadmapItemsResult);
    setRoadmapActualRows(roadmapActualsResult);
    setDrafts({});
  }

  useEffect(() => {
    if (!productRef) return;
    setLoading(true);
    loadData()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load product"))
      .finally(() => setLoading(false));
  }, [productRef, fiscalYear]);

  useEffect(() => {
    if (!forecastLineBucketId && tables?.buckets[0]) {
      setForecastLineBucketId(String(tables.buckets[0].bucket_id));
    }
  }, [forecastLineBucketId, tables]);

  function updateDraft(bucket: BucketTable, row: BucketTableRow, cell: MonthCell, value: string) {
    const key = draftKey(bucket, row, cell);
    setDrafts((current) => {
      const next = { ...current };
      if (value === String(cell.forecast_hours)) {
        delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
  }

  async function saveForecastCell(bucket: BucketTable, row: BucketTableRow, cell: MonthCell) {
    if (productId === null) return;
    const key = draftKey(bucket, row, cell);
    const draft = drafts[key];
    if (draft === undefined) return;

    const value = draft.trim() === "" ? 0 : Number(draft);
    if (!Number.isFinite(value) || value < 0) return;

    if (value === cell.forecast_hours) {
      setDrafts((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      return;
    }

    setSavingCells((current) => ({ ...current, [key]: true }));
    setError(null);
    try {
      await api.upsertForecast({
        product_id: productId,
        team_member_id: row.team_member_id,
        bucket_id: bucket.bucket_id,
        fiscal_month_id: cell.fiscal_month_id,
        hours: value,
      });
      setDrafts((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save forecast");
    } finally {
      setSavingCells((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
    }
  }

  async function addProductTeamMember(teamMemberId: number) {
    if (productId === null) return;
    await api.addProductTeamMember(productId, {
      team_member_id: teamMemberId,
      status: "active",
    });
    await loadData();
  }

  const existingForecastLineKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const bucket of tables?.buckets ?? []) {
      for (const row of bucket.rows) {
        keys.add(forecastLineKey(row.team_member_id, bucket.bucket_id));
      }
    }
    return keys;
  }, [tables]);
  const roleCostSummary = useMemo(() => buildProductRoleCostSummary(productTeam, tables), [productTeam, tables]);

  async function addForecastLine(teamMemberId: number, bucketId: number) {
    if (!tables || productId === null) return;
    if (existingForecastLineKeys.has(forecastLineKey(teamMemberId, bucketId))) {
      setForecastLineMessage("That forecast line already exists.");
      return;
    }

    const member = teamMembers.find((item) => item.id === teamMemberId);
    const bucket = tables.buckets.find((item) => item.bucket_id === bucketId);

    setForecastLineSaving(true);
    setForecastLineMessage(null);
    setError(null);
    try {
      const assignment = productTeam.find((item) => item.team_member_id === teamMemberId);
      if (!assignment) {
        await api.addProductTeamMember(productId, { team_member_id: teamMemberId, status: "active" });
      } else if (assignment.status !== "active") {
        await api.updateProductTeamMember(productId, assignment.id, { status: "active" });
      }
      await api.upsertForecast({
        product_id: productId,
        team_member_id: teamMemberId,
        bucket_id: bucketId,
        fiscal_year: fiscalYear,
        month_sequence: 1,
        hours: 0,
      });
      setForecastLineMemberId("");
      setForecastLineMessage(`${member?.name ?? "Team member"} added to ${bucket?.name ?? "the selected bucket"} for ${fiscalYearLabel}.`);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add forecast line");
    } finally {
      setForecastLineSaving(false);
    }
  }

  async function updateProductTeamMember(assignmentId: number, payload: { status?: string }) {
    if (productId === null) return;
    await api.updateProductTeamMember(productId, assignmentId, payload);
    await loadData();
  }

  async function removeProductTeamMember(assignmentId: number) {
    if (productId === null) return;
    await api.removeProductTeamMember(productId, assignmentId);
    await loadData();
  }

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!summary || !tables) return null;

  const visibleBuckets = tables.buckets.filter((bucket) => bucket.rows.length > 0);
  const hasActualDistribution = distribution.some((row) => row.hours > 0);
  const chartDistribution = hasActualDistribution ? distribution : [{ bucket: "No actuals yet", hours: 1 }];

  return (
    <div className="space-y-6">
      <section className="flex flex-col justify-between gap-4 border-b pb-5 lg:flex-row lg:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold">{summary.product.name}</h1>
            {productSpaces.length ? (
              productSpaces.map((space) => (
                <Badge key={space.id} className={space.is_active ? "" : "border-muted text-muted-foreground"}>
                  {space.jira_project_key}
                </Badge>
              ))
            ) : (
              <Badge>No Jira Spaces</Badge>
            )}
            <Badge className={summary.product.is_active ? "border-primary/40 text-primary" : "border-muted text-muted-foreground"}>
              {summary.product.is_active ? "Active" : "Inactive"}
            </Badge>
            {summary.product.office ? (
              <Badge className="border-muted-foreground/30 bg-muted text-muted-foreground">Office: {summary.product.office}</Badge>
            ) : null}
            {summary.product.division ? (
              <Badge className="border-muted-foreground/30 bg-muted text-muted-foreground">Division: {summary.product.division}</Badge>
            ) : null}
          </div>
          {summary.product.description ? (
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{summary.product.description}</p>
          ) : null}
        </div>
        <PageNav />
      </section>

      <section className="space-y-3">
        <BudgetTracker
          budget={summary.budget_amount}
          forecastSpend={summary.forecasted_cost}
          actualSpend={summary.fytd_cost}
          contextLabel={`${summary.product.name} budget, forecast, and actuals`}
        />
        <ProductRoleCostCard summary={roleCostSummary} />
        <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
          <div className="rounded-lg border bg-card p-4">
            <h2 className="mb-3 text-sm font-semibold uppercase text-muted-foreground">FYTD Actualized Hours</h2>
            <div className="relative h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartDistribution}
                    dataKey="hours"
                    nameKey="bucket"
                    innerRadius={56}
                    outerRadius={88}
                    paddingAngle={hasActualDistribution ? 2 : 0}
                  >
                    {chartDistribution.map((entry, index) => (
                      <Cell key={entry.bucket} fill={hasActualDistribution ? PIE_COLORS[index % PIE_COLORS.length] : "hsl(var(--muted))"} />
                    ))}
                  </Pie>
                  {hasActualDistribution ? <Tooltip formatter={(value: number) => `${formatHours(value)} hrs`} /> : null}
                  {hasActualDistribution ? <Legend /> : null}
                </PieChart>
              </ResponsiveContainer>
              {!hasActualDistribution ? (
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
                  <div className="text-sm font-semibold text-muted-foreground">No FYTD actuals yet</div>
                  <div className="mt-1 max-w-44 text-xs text-muted-foreground">Actualized hours will appear here after Jira syncs worklogs for this fiscal year.</div>
                </div>
              ) : null}
            </div>
          </div>
          <ProductSnapshotPanel summary={summary} />
        </div>
      </section>

      <ProductRoadmapItemsSection actualRows={roadmapActualRows} items={roadmapItems} />
      <RoadmapActualsTable rows={roadmapActualRows} showTeamMember title="Roadmap Actuals For Billing" />

      <ProductTeamSection
        assignments={productTeam}
        members={teamMembers}
        onAdd={addProductTeamMember}
        onRemove={removeProductTeamMember}
        onUpdate={updateProductTeamMember}
      />

      <ForecastLineSection
        assignments={productTeam}
        buckets={tables.buckets}
        existingLineKeys={existingForecastLineKeys}
        members={teamMembers}
        message={forecastLineMessage}
        onAdd={addForecastLine}
        saving={forecastLineSaving}
        selectedBucketId={forecastLineBucketId}
        selectedMemberId={forecastLineMemberId}
        setSelectedBucketId={setForecastLineBucketId}
        setSelectedMemberId={setForecastLineMemberId}
      />

      <section className="space-y-5">
        {visibleBuckets.length ? (
          visibleBuckets.map((bucket) => (
            <BucketSection
              key={bucket.bucket_id}
              bucket={bucket}
              drafts={drafts}
              onDraftChange={updateDraft}
              onDraftCommit={saveForecastCell}
              savingCells={savingCells}
            />
          ))
        ) : (
          <div className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">
            No forecast lines exist for this product yet. Add a Product Team member, then create a forecast line for the bucket they will support.
          </div>
        )}
      </section>

      <ReportedValuesTable rows={reportedRows} showTeamMember />
    </div>
  );
}

function ProductRoleCostCard({ summary }: { summary: ProductRoleCostSummary }) {
  const maxCost = Math.max(...summary.rows.map((row) => row.forecastCost), 0);

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex flex-col justify-between gap-2 md:flex-row md:items-start">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Role Cost Summary</h2>
          <p className="mt-1 text-sm text-muted-foreground">De-identified FY forecast cost by Product Team role.</p>
        </div>
        <div className="numeric-cell text-sm font-semibold text-primary">
          {formatMemberCount(summary.totalMembers)} / {formatCurrency(summary.totalCost)}
        </div>
      </div>
      {summary.rows.length ? (
        <div className="overflow-hidden rounded-md border bg-background">
          {summary.rows.map((row) => (
            <div key={row.role} className="grid gap-3 border-b px-3 py-2.5 last:border-b-0 lg:grid-cols-[11rem_1fr_8rem] lg:items-center">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-foreground">{row.role}</div>
                <div className="text-xs text-muted-foreground">{formatMemberCount(row.memberCount)}</div>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-[color:var(--spark-cyan)]"
                  style={{ width: `${maxCost > 0 ? Math.max((row.forecastCost / maxCost) * 100, 4) : 0}%` }}
                />
              </div>
              <div className="numeric-cell text-left text-sm font-semibold text-primary lg:text-right">
                {formatCurrency(row.forecastCost)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-md bg-secondary/50 p-3 text-sm text-muted-foreground">No active product team members yet.</div>
      )}
    </section>
  );
}

function ProductSnapshotPanel({ summary }: { summary: ProductSummary }) {
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="text-sm font-semibold uppercase text-muted-foreground">FY Snapshot</h2>
      <div className="mt-3 grid gap-4 lg:grid-cols-2">
        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase text-muted-foreground">Hours</div>
          <SnapshotRow label="Actualized FYTD" value={formatHours(summary.fytd_hours)} />
          <SnapshotRow label="Forecasted FY" value={formatHours(summary.forecasted_hours)} />
          <SnapshotRow label="Remaining" value={formatHours(summary.remaining_hours)} />
        </div>
        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase text-muted-foreground">Cost</div>
          <SnapshotRow label="Actualized FYTD" value={formatCurrency(summary.fytd_cost)} />
          <SnapshotRow label="Forecasted FY" value={formatCurrency(summary.forecasted_cost)} />
          <SnapshotRow label="Remaining" value={formatCurrency(summary.remaining_cost)} />
        </div>
      </div>
    </section>
  );
}

function SnapshotRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 rounded-md bg-secondary/50 px-3 py-2">
      <span className="truncate text-sm text-muted-foreground">{label}</span>
      <span className="numeric-cell shrink-0 text-base font-semibold text-primary">{value}</span>
    </div>
  );
}

function ProductRoadmapItemsSection({ actualRows, items }: { actualRows: RoadmapActualRow[]; items: RoadmapItem[] }) {
  const actualsByRoadmapItem = buildRoadmapItemActualSummaries(actualRows);
  const linkedTickets = items.reduce((total, item) => total + item.linked_issue_count, 0);
  const programAreas = new Set(items.map((item) => item.program_area || "Unassigned"));
  const mappedActualHours = Array.from(actualsByRoadmapItem.values()).reduce((total, row) => total + row.actualHours, 0);
  const mappedActualCost = Array.from(actualsByRoadmapItem.values()).reduce((total, row) => total + row.actualCost, 0);
  const gapTickets = new Set<string>();
  actualRows.forEach((row) => {
    if (row.mapping_status !== "mapped") {
      row.ticket_keys.forEach((ticketKey) => gapTickets.add(ticketKey));
    }
  });

  return (
    <section className="space-y-3">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <h2 className="text-lg font-semibold">Roadmap Items</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Roadmap Items mapped to this product. Actual billing appears separately after Jira worklogs are synced.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <RoadmapItemMetric label="Items" value={String(items.length)} />
          <RoadmapItemMetric label="Tickets" value={String(linkedTickets)} />
          <RoadmapItemMetric label="Actual Hrs" value={formatHours(mappedActualHours)} />
          <RoadmapItemMetric label="Actual Cost" value={formatCurrency(mappedActualCost)} />
          <RoadmapItemMetric label="Gaps" value={String(gapTickets.size)} tone={gapTickets.size ? "warn" : "default"} />
          <RoadmapItemMetric label="Programs" value={String(programAreas.size)} />
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1180px] text-sm">
            <thead>
              <tr className="border-b bg-secondary/60">
                <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">Roadmap Item</th>
                <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">Status</th>
                <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">Bucket</th>
                <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">Jira Category</th>
                <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">Program Area</th>
                <th className="px-3 py-3 text-right text-xs font-semibold uppercase text-muted-foreground">Linked Tickets</th>
                <th className="px-3 py-3 text-right text-xs font-semibold uppercase text-muted-foreground">Actual Hrs</th>
                <th className="px-3 py-3 text-right text-xs font-semibold uppercase text-muted-foreground">Actual Cost</th>
                <th className="px-3 py-3 text-right text-xs font-semibold uppercase text-muted-foreground">Team Members</th>
              </tr>
            </thead>
            <tbody>
              {items.length ? (
                items.map((item) => {
                  const actualSummary = actualsByRoadmapItem.get(item.id);
                  return (
                    <tr key={item.id} className="border-b last:border-0">
                      <td className="px-3 py-3">
                        <div className="font-medium text-primary">
                          {item.source_url ? (
                            <a href={item.source_url} target="_blank" rel="noreferrer">
                              {item.jira_issue_key}
                            </a>
                          ) : (
                            item.jira_issue_key
                          )}
                        </div>
                        <div className="max-w-[36rem] truncate text-sm text-foreground" title={item.title}>
                          {item.title}
                        </div>
                        <div className="text-xs text-muted-foreground">{roadmapItemLinkContext(item)}</div>
                      </td>
                      <td className="px-3 py-3">{item.status ?? "No status"}</td>
                      <td className="px-3 py-3">{item.bucket ?? "Unmapped"}</td>
                      <td className="px-3 py-3">{item.source_category || "Not set"}</td>
                      <td className="px-3 py-3">{item.program_area || "Unassigned"}</td>
                      <td className="numeric-cell px-3 py-3 text-right font-semibold">{item.linked_issue_count}</td>
                      <td className="numeric-cell px-3 py-3 text-right font-semibold">{formatHours(actualSummary?.actualHours ?? 0)}</td>
                      <td className="numeric-cell px-3 py-3 text-right font-semibold text-primary">{formatCurrency(actualSummary?.actualCost ?? 0)}</td>
                      <td className="numeric-cell px-3 py-3 text-right">{actualSummary?.teamMembers.size ?? 0}</td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td className="px-3 py-5 text-sm text-muted-foreground" colSpan={9}>
                    No Roadmap Items are mapped to this product yet. Use Admin / Jira / Roadmap Item Mapping to attach Roadmap Items to this product.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function RoadmapItemMetric({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "warn" }) {
  return (
    <div className="rounded-md bg-secondary px-3 py-2">
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <div className={`numeric-cell text-right text-base font-semibold ${tone === "warn" ? "text-warning" : "text-primary"}`}>{value}</div>
    </div>
  );
}

type RoadmapItemActualSummary = {
  actualHours: number;
  actualCost: number;
  tickets: Set<string>;
  teamMembers: Set<number>;
};

function buildRoadmapItemActualSummaries(rows: RoadmapActualRow[]) {
  const summaries = new Map<number, RoadmapItemActualSummary>();
  rows.forEach((row) => {
    if (row.roadmap_item_id === null) return;
    const summary =
      summaries.get(row.roadmap_item_id) ??
      ({
        actualHours: 0,
        actualCost: 0,
        tickets: new Set<string>(),
        teamMembers: new Set<number>(),
      } satisfies RoadmapItemActualSummary);
    summary.actualHours += row.actual_hours;
    summary.actualCost += row.actual_cost;
    summary.teamMembers.add(row.team_member_id);
    row.ticket_keys.forEach((ticketKey) => summary.tickets.add(ticketKey));
    summaries.set(row.roadmap_item_id, summary);
  });
  return summaries;
}

function roadmapItemLinkContext(item: RoadmapItem) {
  const deliverables = (item.linked_issues ?? []).filter((link) => (link.issue_type ?? "").toLowerCase() === "deliverable");
  if (!deliverables.length) return item.issue_type ?? "Roadmap Item";
  const visibleKeys = deliverables.slice(0, 3).map((link) => link.jira_issue_key);
  const hiddenCount = deliverables.length - visibleKeys.length;
  return `Deliverables: ${visibleKeys.join(", ")}${hiddenCount > 0 ? ` +${hiddenCount}` : ""}`;
}

function ProductTeamSection({
  assignments,
  members,
  onAdd,
  onRemove,
  onUpdate,
}: {
  assignments: ProductTeamMember[];
  members: TeamMember[];
  onAdd: (teamMemberId: number) => Promise<void>;
  onRemove: (assignmentId: number) => Promise<void>;
  onUpdate: (assignmentId: number, payload: { status?: string }) => Promise<void>;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedMemberId, setSelectedMemberId] = useState("");
  const [saving, setSaving] = useState(false);
  const rosterId = useId();
  const assignedMemberIds = new Set(assignments.map((assignment) => assignment.team_member_id));
  const availableMembers = members.filter((member) => !assignedMemberIds.has(member.id));
  const activeCount = assignments.filter((assignment) => assignment.status === "active").length;
  const inactiveCount = assignments.length - activeCount;

  async function addAssignment() {
    const teamMemberId = Number(selectedMemberId);
    if (!Number.isFinite(teamMemberId) || teamMemberId <= 0) return;
    setSaving(true);
    try {
      await onAdd(teamMemberId);
      setSelectedMemberId("");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-lg font-semibold">Product Team</h2>
          <p className="text-sm text-muted-foreground">
            Assign rostered team members to this product. Forecast bucket rows are managed in Forecast Lines; Jira actuals use ticket work type.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:items-end">
          <div className="flex flex-wrap gap-2 text-sm">
            <Badge>{assignments.length} assigned</Badge>
            <Badge>{activeCount} active</Badge>
            {inactiveCount ? <Badge>{inactiveCount} inactive</Badge> : null}
          </div>
          <Button
            aria-controls={rosterId}
            aria-expanded={isExpanded}
            className="w-full sm:w-auto"
            onClick={() => setIsExpanded((current) => !current)}
            size="sm"
            type="button"
            variant="outline"
          >
            {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            {isExpanded ? "Hide roster" : "Show roster"}
          </Button>
        </div>
      </div>

      {isExpanded ? (
        <div className="space-y-3" id={rosterId}>
          <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
            <select
              aria-label="Team member to add"
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
              disabled={saving || availableMembers.length === 0}
              value={selectedMemberId}
              onChange={(event) => setSelectedMemberId(event.target.value)}
            >
              <option value="">{availableMembers.length ? "Select team member" : "All members assigned"}</option>
              {availableMembers.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.name}
                </option>
              ))}
            </select>
            <Button onClick={addAssignment} disabled={saving || !selectedMemberId}>
              <UserPlus className="h-4 w-4" />
              Add
            </Button>
          </div>

          <div className="overflow-hidden rounded-lg border bg-card">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[780px] text-sm">
                <thead>
                  <tr className="border-b bg-secondary/60">
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">Team Member</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">Role</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">Team</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">Bill Rate</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">Status</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">History</th>
                    <th className="px-3 py-3 text-right text-xs font-semibold uppercase text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {assignments.length ? (
                    assignments.map((assignment) => (
                      <tr key={assignment.id} className="border-b last:border-0">
                        <td className="px-3 py-3">
                          <Link className="font-medium text-primary hover:underline" to={teamMemberDetailPath(assignment)}>
                            {assignment.team_member}
                          </Link>
                        </td>
                        <td className="px-3 py-3">{assignment.role}</td>
                        <td className="px-3 py-3">{assignment.team}</td>
                        <td className="numeric-cell px-3 py-3">{formatCurrency(assignment.bill_rate)}/hr</td>
                        <td className="px-3 py-3">
                          <select
                            aria-label={`${assignment.team_member} product status`}
                            className="h-8 rounded-md border border-input bg-background px-2 text-sm"
                            value={assignment.status}
                            onChange={(event) => void onUpdate(assignment.id, { status: event.target.value })}
                          >
                            <option value="active">Active</option>
                            <option value="inactive">Inactive</option>
                          </select>
                        </td>
                        <td className="px-3 py-3 text-muted-foreground">
                          {assignment.has_forecast_entries
                            ? "Forecast lines clear on remove"
                            : assignment.has_actual_entries
                              ? "Actuals retained"
                              : "No hours yet"}
                        </td>
                        <td className="px-3 py-3 text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              const confirmed = window.confirm(
                                `Remove ${assignment.team_member} from this product? Forecast lines for this product will be deleted. Jira actuals will stay for historical reporting.`,
                              );
                              if (confirmed) void onRemove(assignment.id);
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                            Remove
                          </Button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="px-3 py-5 text-sm text-muted-foreground" colSpan={7}>
                        No team members assigned to this product yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function ForecastLineSection({
  assignments,
  buckets,
  existingLineKeys,
  members,
  message,
  onAdd,
  saving,
  selectedBucketId,
  selectedMemberId,
  setSelectedBucketId,
  setSelectedMemberId,
}: {
  assignments: ProductTeamMember[];
  buckets: BucketTable[];
  existingLineKeys: Set<string>;
  members: TeamMember[];
  message: string | null;
  onAdd: (teamMemberId: number, bucketId: number) => Promise<void>;
  saving: boolean;
  selectedBucketId: string;
  selectedMemberId: string;
  setSelectedBucketId: (value: string) => void;
  setSelectedMemberId: (value: string) => void;
}) {
  const selectedMember = Number(selectedMemberId);
  const selectedBucket = Number(selectedBucketId);
  const duplicateLine =
    Number.isFinite(selectedMember) &&
    selectedMember > 0 &&
    Number.isFinite(selectedBucket) &&
    selectedBucket > 0 &&
    existingLineKeys.has(forecastLineKey(selectedMember, selectedBucket));
  const activeProductTeamMemberIds = new Set(
    assignments.filter((assignment) => assignment.status === "active").map((assignment) => assignment.team_member_id),
  );
  const activeMembers = [...members]
    .filter((member) => member.status === "active" && activeProductTeamMemberIds.has(member.id))
    .sort((left, right) => left.name.localeCompare(right.name));
  const selectedMemberIsInProductTeam = selectedMemberId === "" || activeProductTeamMemberIds.has(selectedMember);

  useEffect(() => {
    if (!selectedMemberIsInProductTeam) {
      setSelectedMemberId("");
    }
  }, [selectedMemberIsInProductTeam, setSelectedMemberId]);

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-end">
        <div>
          <h2 className="text-lg font-semibold">Forecast Lines</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Add one planning row per Product Team member and bucket. The same person can have Net New, Enhance, and Maintenance rows.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            aria-label="Forecast line team member"
            className="h-9 min-w-52 rounded-md border border-input bg-background px-2 text-sm"
            disabled={saving || activeMembers.length === 0}
            value={selectedMemberId}
            onChange={(event) => setSelectedMemberId(event.target.value)}
          >
            <option value="">{activeMembers.length ? "Select product team member" : "Add Product Team first"}</option>
            {activeMembers.map((member) => (
              <option key={member.id} value={member.id}>
                {member.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Forecast line bucket"
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            disabled={saving || buckets.length === 0}
            value={selectedBucketId}
            onChange={(event) => setSelectedBucketId(event.target.value)}
          >
            {buckets.map((bucket) => (
              <option key={bucket.bucket_id} value={bucket.bucket_id}>
                {bucket.name}
              </option>
            ))}
          </select>
          <Button
            onClick={() => void onAdd(selectedMember, selectedBucket)}
            disabled={saving || !selectedMemberId || !selectedBucketId || duplicateLine || !selectedMemberIsInProductTeam}
          >
            <Plus className="h-4 w-4" />
            {saving ? "Adding" : "Add Forecast Line"}
          </Button>
        </div>
      </div>
      {!activeMembers.length ? <div className="mt-3 text-sm text-muted-foreground">Add active members to Product Team before creating forecast lines.</div> : null}
      {duplicateLine ? <div className="mt-3 text-sm text-muted-foreground">That line already exists. Edit its monthly forecast cells below.</div> : null}
      {message ? <div className="mt-3 text-sm text-primary">{message}</div> : null}
    </section>
  );
}

function BucketSection({
  bucket,
  drafts,
  onDraftChange,
  onDraftCommit,
  savingCells,
}: {
  bucket: BucketTable;
  drafts: Record<string, string>;
  onDraftChange: (bucket: BucketTable, row: BucketTableRow, cell: MonthCell, value: string) => void;
  onDraftCommit: (bucket: BucketTable, row: BucketTableRow, cell: MonthCell) => void;
  savingCells: Record<string, boolean>;
}) {
  const monthlyTotals =
    bucket.rows[0]?.months.map((month, index) => {
      return bucket.rows.reduce(
        (acc, row) => {
          const cell = row.months[index];
          acc.forecast += cell.forecast_hours;
          acc.actual += cell.actual_hours;
          acc.cost += cell.forecast_cost;
          acc.variance += cell.variance_cost;
          return acc;
        },
        { fiscalMonthId: month.fiscal_month_id, forecast: 0, actual: 0, cost: 0, variance: 0 },
      );
    }) ?? [];

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{bucket.name}</h2>
        <div className="text-right">
          <div className="numeric-cell text-sm text-muted-foreground">
            {formatHours(bucket.totals.forecast_hours)} forecast / {formatHours(bucket.totals.actual_hours)} actual
          </div>
          <div className="text-xs text-muted-foreground">Cost variance = actual - forecast</div>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full table-fixed border-collapse text-xs">
            <colgroup>
              <col className="w-32" />
              <col className="w-24" />
              {bucket.rows[0]?.months.map((month) => <col key={month.fiscal_month_id} className="w-16" />)}
              <col className="w-24" />
            </colgroup>
            <thead>
              <tr className="border-b bg-secondary/60">
                <th className="sticky left-0 z-10 bg-secondary px-2 py-2 text-left text-[11px] font-semibold uppercase text-muted-foreground">
                  Team Member
                </th>
                <th className="sticky left-32 z-10 bg-secondary px-2 py-2 text-left text-[11px] font-semibold uppercase text-muted-foreground">
                  Metric
                </th>
                {bucket.rows[0]?.months.map((month) => (
                  <th key={month.fiscal_month_id} className="px-1 py-2 text-right text-[11px] font-semibold uppercase text-muted-foreground">
                    {month.label}
                  </th>
                ))}
                <th className="px-1 py-2 text-right text-[11px] font-semibold uppercase text-muted-foreground">FY Total</th>
              </tr>
            </thead>
            <tbody>
              {bucket.rows.map((row) => (
                <Fragment key={row.team_member_id}>
                  <tr className="border-t align-middle">
                    <td rowSpan={4} className="sticky left-0 z-10 bg-card px-2 py-2 align-top">
                      <Link className="block truncate font-medium text-primary hover:underline" to={teamMemberDetailPath(row)}>
                        {row.team_member}
                      </Link>
                      <div className="numeric-cell mt-1 truncate text-[11px] text-muted-foreground">{formatCurrency(row.bill_rate)}/hr</div>
                    </td>
                    <MetricLabel label="Forecast" />
                    {row.months.map((cell) => (
                      <td key={cell.fiscal_month_id} className="px-1 py-1">
                        <ForecastInput
                          bucket={bucket}
                          row={row}
                          cell={cell}
                          value={drafts[draftKey(bucket, row, cell)] ?? String(cell.forecast_hours)}
                          dirty={drafts[draftKey(bucket, row, cell)] !== undefined}
                          saving={savingCells[draftKey(bucket, row, cell)] === true}
                          onChange={(value) => onDraftChange(bucket, row, cell, value)}
                          onCommit={() => onDraftCommit(bucket, row, cell)}
                        />
                      </td>
                    ))}
                    <ValueCell value={formatHours(row.totals.forecast_hours)} strong />
                  </tr>
                  <tr>
                    <MetricLabel label="Actual" muted />
                    {row.months.map((cell) => (
                      <ValueCell key={cell.fiscal_month_id} value={formatHours(cell.actual_hours)} muted />
                    ))}
                    <ValueCell value={formatHours(row.totals.actual_hours)} muted strong />
                  </tr>
                  <tr>
                    <MetricLabel label="Fcst $" />
                    {row.months.map((cell) => (
                      <ValueCell key={cell.fiscal_month_id} value={formatCurrency(cell.forecast_cost)} />
                    ))}
                    <ValueCell value={formatCurrency(row.totals.forecast_cost)} strong />
                  </tr>
                  <tr className="border-b">
                    <MetricLabel label="Actual-Fcst $" title={COST_VARIANCE_HELP} />
                    {row.months.map((cell) => (
                      <ValueCell
                        key={cell.fiscal_month_id}
                        value={formatCurrency(cell.variance_cost)}
                        className={varianceCostClassName(cell.variance_cost)}
                      />
                    ))}
                    <ValueCell
                      value={formatCurrency(row.totals.variance_cost)}
                      className={varianceCostClassName(row.totals.variance_cost)}
                      strong
                    />
                  </tr>
                </Fragment>
              ))}
              <tr className="border-t bg-secondary/50 font-semibold">
                <td rowSpan={4} className="sticky left-0 z-10 bg-secondary px-2 py-2 align-top">
                  Bucket Total
                </td>
                <MetricLabel label="Forecast" total />
                {monthlyTotals.map((totals) => (
                  <ValueCell key={totals.fiscalMonthId} value={formatHours(totals.forecast)} total strong />
                ))}
                <ValueCell value={formatHours(bucket.totals.forecast_hours)} total strong />
              </tr>
              <tr className="bg-secondary/50 font-semibold">
                <MetricLabel label="Actual" muted total />
                {monthlyTotals.map((totals) => (
                  <ValueCell key={totals.fiscalMonthId} value={formatHours(totals.actual)} muted total strong />
                ))}
                <ValueCell value={formatHours(bucket.totals.actual_hours)} muted total strong />
              </tr>
              <tr className="bg-secondary/50 font-semibold">
                <MetricLabel label="Fcst $" total />
                {monthlyTotals.map((totals) => (
                  <ValueCell key={totals.fiscalMonthId} value={formatCurrency(totals.cost)} total strong />
                ))}
                <ValueCell value={formatCurrency(bucket.totals.forecast_cost)} total strong />
              </tr>
              <tr className="bg-secondary/50 font-semibold">
                <MetricLabel label="Actual-Fcst $" title={COST_VARIANCE_HELP} total />
                {monthlyTotals.map((totals) => (
                  <ValueCell
                    key={totals.fiscalMonthId}
                    value={formatCurrency(totals.variance)}
                    className={varianceCostClassName(totals.variance)}
                    total
                    strong
                  />
                ))}
                <ValueCell
                  value={formatCurrency(bucket.totals.variance_cost)}
                  className={varianceCostClassName(bucket.totals.variance_cost)}
                  total
                  strong
                />
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function ForecastInput({
  bucket,
  row,
  cell,
  value,
  dirty,
  saving,
  onChange,
  onCommit,
}: {
  bucket: BucketTable;
  row: BucketTableRow;
  cell: MonthCell;
  value: string;
  dirty: boolean;
  saving: boolean;
  onChange: (value: string) => void;
  onCommit: () => void;
}) {
  const numericValue = Number(value);
  const invalid = value !== "" && (!Number.isFinite(numericValue) || numericValue < 0);
  return (
    <Input
      aria-label={`${bucket.name} ${row.team_member} ${cell.label} forecast hours`}
      className={`numeric-cell h-7 min-w-0 px-1 text-right text-xs ${dirty ? "border-primary bg-primary/5" : ""} ${
        invalid ? "border-destructive" : ""
      } ${saving ? "opacity-70" : ""}`}
      disabled={saving}
      inputMode="decimal"
      pattern="[0-9]*"
      type="text"
      value={value}
      onBlur={onCommit}
      onChange={(event) => onChange(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.currentTarget.blur();
        }
      }}
    />
  );
}

function MetricLabel({ label, muted, title, total }: { label: string; muted?: boolean; title?: string; total?: boolean }) {
  return (
    <td
      aria-label={title ? `${label}: ${title}` : label}
      className={`sticky left-32 z-10 px-2 py-1.5 text-[11px] font-semibold uppercase ${
        total ? "bg-secondary" : "bg-card"
      } ${muted ? "text-muted-foreground" : "text-foreground"}`}
      title={title}
    >
      {label}
    </td>
  );
}

function varianceCostClassName(value: number) {
  if (value > 0) {
    return "text-destructive";
  }
  if (value < 0) {
    return "text-primary";
  }
  return "text-muted-foreground";
}

function ValueCell({
  value,
  muted,
  strong,
  total,
  className,
}: {
  value: string;
  muted?: boolean;
  strong?: boolean;
  total?: boolean;
  className?: string;
}) {
  return (
    <td className={`numeric-cell px-1 py-1.5 text-right text-xs ${total ? "bg-secondary/50" : ""} ${muted ? "text-muted-foreground" : ""}`}>
      <span className={`block truncate ${strong ? "font-semibold" : "font-medium"} ${className ?? ""}`}>{value}</span>
    </td>
  );
}

function draftKey(bucket: BucketTable, row: BucketTableRow, cell: MonthCell) {
  return `${bucket.bucket_id}:${row.team_member_id}:${cell.fiscal_month_id}`;
}

function forecastLineKey(teamMemberId: number, bucketId: number) {
  return `${teamMemberId}:${bucketId}`;
}

function formatMemberCount(count: number) {
  return `${count} team ${count === 1 ? "member" : "members"}`;
}

function buildProductRoleCostSummary(assignments: ProductTeamMember[], tables: ProductBucketTables | null): ProductRoleCostSummary {
  const activeAssignments = assignments.filter((assignment) => assignment.status === "active");
  const activeMemberRoles = new Map(activeAssignments.map((assignment) => [assignment.team_member_id, assignment.role || "Unspecified"]));
  const rowsByRole = new Map<string, ProductRoleCostRow>();

  for (const assignment of activeAssignments) {
    const role = assignment.role || "Unspecified";
    const current = rowsByRole.get(role) ?? { role, memberCount: 0, forecastCost: 0 };
    current.memberCount += 1;
    rowsByRole.set(role, current);
  }

  for (const bucket of tables?.buckets ?? []) {
    for (const row of bucket.rows) {
      const role = activeMemberRoles.get(row.team_member_id);
      if (!role) continue;
      const current = rowsByRole.get(role) ?? { role, memberCount: 0, forecastCost: 0 };
      current.forecastCost += row.totals.forecast_cost;
      rowsByRole.set(role, current);
    }
  }

  const rows = [...rowsByRole.values()].sort(
    (left, right) => right.forecastCost - left.forecastCost || right.memberCount - left.memberCount || left.role.localeCompare(right.role),
  );

  return {
    rows,
    totalMembers: activeAssignments.length,
    totalCost: rows.reduce((total, row) => total + row.forecastCost, 0),
  };
}
