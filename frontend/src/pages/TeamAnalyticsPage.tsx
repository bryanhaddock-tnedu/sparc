import { ArrowLeft, Plus, Save } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { MetricCard } from "../components/MetricCard";
import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { TeamMemberRankingsTable } from "../components/TeamMemberRankingsTable";
import { TeamMemberNameLink } from "../components/TeamMemberNameLink";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import { productDetailPath } from "../lib/routes";
import {
  DELIVERY_FLOW_STAGE_LABELS,
  DELIVERY_FLOW_STAGE_ORDER,
  buildTeamDeliveryFlowAnalytics,
  buildSingleTeamAnalytics,
  buildTeamMemberRankingRows,
  teamDisplayNameFromRef,
  teamAnalyticsPath,
  type TeamAnalytics,
  type TeamAnalyticsBreakdownRow,
  type TeamDeliveryFlowAnalytics,
  type TeamDeliveryFlowStageSummary,
  type TeamRankingDimension,
} from "../lib/teamAnalytics";
import { formatHours } from "../lib/utils";
import type {
  DeliveryFlowIssue,
  RoadmapForecastAllocationUpsertPayload,
  ReportedValueRow,
  TeamMember,
  TeamMemberStoryPointMetric,
  TeamRoadmapForecastPlan,
  TeamRoadmapForecastRow,
} from "../types/api";

const PLANNER_AUTOSAVE_DELAY_MS = 700;

export function TeamAnalyticsPage() {
  const params = useParams();
  const navigate = useNavigate();
  const teamRef = safeDecodeURIComponent(params.teamSlug ?? "");
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [reportedRows, setReportedRows] = useState<ReportedValueRow[]>([]);
  const [storyMetrics, setStoryMetrics] = useState<TeamMemberStoryPointMetric[]>([]);
  const [deliveryIssues, setDeliveryIssues] = useState<DeliveryFlowIssue[]>([]);
  const [roadmapPlan, setRoadmapPlan] = useState<TeamRoadmapForecastPlan | null>(null);
  const [rankingDimension, setRankingDimension] = useState<TeamRankingDimension>("fytd_actual");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [plannerSaving, setPlannerSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.teamMembers(),
      api.reportedValues({}, fiscalYear),
      api.teamMemberStoryPointMetrics(fiscalYear),
      api.deliveryFlowIssues(fiscalYear),
      api.teamRoadmapForecastPlan(teamRef, fiscalYear),
    ])
      .then(([memberRows, reportedValueRows, storyPointRows, deliveryFlowRows, roadmapPlanRows]) => {
        setMembers(memberRows);
        setReportedRows(reportedValueRows);
        setStoryMetrics(storyPointRows);
        setDeliveryIssues(deliveryFlowRows);
        setRoadmapPlan(roadmapPlanRows);
        setError(null);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load team analytics"))
      .finally(() => setLoading(false));
  }, [fiscalYear, teamRef]);

  const teamName = useMemo(() => teamDisplayNameFromRef(teamRef, members), [members, teamRef]);
  const analytics = useMemo(() => buildSingleTeamAnalytics(teamName, members, reportedRows, fiscalYear), [fiscalYear, members, reportedRows, teamName]);
  const rankingRows = useMemo(
    () => buildTeamMemberRankingRows(reportedRows, members, fiscalYear, storyMetrics, teamName),
    [fiscalYear, members, reportedRows, storyMetrics, teamName],
  );
  const deliveryFlow = useMemo(() => buildTeamDeliveryFlowAnalytics(teamName, deliveryIssues), [deliveryIssues, teamName]);

  useEffect(() => {
    if (loading || !teamName) return;
    const cleanPath = teamAnalyticsPath(teamName);
    if (window.location.pathname !== cleanPath) {
      navigate(cleanPath, { replace: true });
    }
  }, [loading, navigate, teamName]);

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;

  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <Button asChild className="mb-3" size="sm" variant="outline">
            <Link to="/team">
              <ArrowLeft className="h-4 w-4" />
              Team Overview
            </Link>
          </Button>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold">{analytics.team}</h1>
            <Badge className="border-primary/40 text-primary">{analytics.activeMembers} active</Badge>
            {analytics.members.length - analytics.activeMembers > 0 ? (
              <Badge className="border-muted text-muted-foreground">{analytics.members.length - analytics.activeMembers} inactive</Badge>
            ) : null}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Team analytics / {fiscalYearLabel} ({fiscalYearRangeLabel})
          </p>
        </div>
        <PageNav current="team" />
      </div>

      {analytics.members.length ? (
        <>
          {notice ? <div className="rounded-md border border-[color:var(--spark-cyan)] bg-accent/10 px-3 py-2 text-sm text-primary">{notice}</div> : null}
          {actionError ? <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{actionError}</div> : null}
          <TeamSummaryCards analytics={analytics} />
          <TeamDeliveryFlowPanel flow={deliveryFlow} />
          {roadmapPlan ? (
            <RoadmapForecastPlanner
              fiscalYear={fiscalYear}
              onError={setActionError}
              onNotice={setNotice}
              onPlanChange={setRoadmapPlan}
              plan={roadmapPlan}
              saving={plannerSaving}
              setSaving={setPlannerSaving}
              teamRef={teamRef}
            />
          ) : null}
          <TeamMonthlyForecastActualCard analytics={analytics} />
          <TeamMemberRankingsTable
            description={`${analytics.team} members with annual capacity, Forecast value, Actual value, and the selected ranking signal.`}
            dimension={rankingDimension}
            onDimensionChange={setRankingDimension}
            rows={rankingRows}
            showTeam={false}
            title="Team Member Rankings"
          />
          <div className="grid gap-4 xl:grid-cols-3">
            <TeamBreakdownTable linkProducts rows={analytics.products} title="Product Mix" />
            <TeamBreakdownTable rows={analytics.workTypes} title="Work Type Mix" />
            <TeamBreakdownTable rows={analytics.roles} title="Role Mix" />
          </div>
        </>
      ) : (
        <div className="rounded-lg border bg-card p-5 text-sm text-muted-foreground">No Team Members found for this team.</div>
      )}
    </div>
  );
}

function safeDecodeURIComponent(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function TeamDeliveryFlowPanel({ flow }: { flow: TeamDeliveryFlowAnalytics }) {
  const stageSummaries = stageSummariesWithDefaults(flow.stages);
  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Delivery Flow</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Unique Jira issues from the latest estimation run, separated so engineering-complete work is not hidden by UAT or business acceptance lag.
          </p>
        </div>
        <div className="text-right text-xs text-muted-foreground">Aging uses latest Jira update date</div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[1.4fr_repeat(4,minmax(0,1fr))]">
        <div className="rounded-lg border border-[color:var(--spark-orange)] bg-[color:var(--spark-orange)]/10 p-4">
          <div className="text-xs font-semibold uppercase text-muted-foreground">Acceptance Queue</div>
          <div className="numeric-cell mt-2 text-3xl font-semibold text-primary">{flow.acceptanceQueue.issueCount}</div>
          <p className="mt-1 text-sm text-muted-foreground">Engineering done or in UAT/business acceptance, but not accepted as Done.</p>
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
            <FlowMiniMetric label="SP" value={formatHours(flow.acceptanceQueue.storyPoints)} />
            <FlowMiniMetric label="Hours" value={formatHours(flow.acceptanceQueue.loggedHours)} />
            <FlowMiniMetric label="Oldest" value={formatDays(flow.acceptanceQueue.oldestUpdatedDaysAgo)} />
          </div>
        </div>

        {stageSummaries
          .filter((summary) => summary.stage !== "blocked")
          .map((summary) => (
            <div key={summary.stage} className="rounded-lg border bg-secondary/30 p-3">
              <div className="text-xs font-semibold uppercase text-muted-foreground">{summary.label}</div>
              <div className="numeric-cell mt-2 text-2xl font-semibold text-primary">{summary.issueCount}</div>
              <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                <div>{formatHours(summary.storyPoints)} SP</div>
                <div>{formatHours(summary.loggedHours)} logged hrs</div>
                <div>{formatDays(summary.oldestUpdatedDaysAgo)} oldest update</div>
              </div>
            </div>
          ))}
      </div>

      <div className="mt-4 overflow-hidden rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Jira Status</TableHead>
              <TableHead>SPARC Stage</TableHead>
              <TableHead className="text-right">Issues</TableHead>
              <TableHead className="text-right">Story Points</TableHead>
              <TableHead className="text-right">Logged Hrs</TableHead>
              <TableHead className="text-right">Oldest Update</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {flow.statuses.length ? (
              flow.statuses.map((status) => (
                <TableRow key={`${status.stage}-${status.status}`}>
                  <TableCell className="font-medium">{status.status}</TableCell>
                  <TableCell>{status.label}</TableCell>
                  <TableCell className="numeric-cell text-right">{status.issueCount}</TableCell>
                  <TableCell className="numeric-cell text-right">{formatHours(status.storyPoints)}</TableCell>
                  <TableCell className="numeric-cell text-right">{formatHours(status.loggedHours)}</TableCell>
                  <TableCell className="numeric-cell text-right">{formatDays(status.oldestUpdatedDaysAgo)}</TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell className="py-5 text-muted-foreground" colSpan={6}>
                  No delivery-flow evidence from the latest estimation run yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

function FlowMiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-card/70 p-2">
      <div className="text-[10px] font-semibold uppercase text-muted-foreground">{label}</div>
      <div className="numeric-cell mt-1 font-semibold text-primary">{value}</div>
    </div>
  );
}

function stageSummariesWithDefaults(summaries: TeamDeliveryFlowStageSummary[]) {
  const summaryByStage = new Map(summaries.map((summary) => [summary.stage, summary]));
  return DELIVERY_FLOW_STAGE_ORDER.map(
    (stage) =>
      summaryByStage.get(stage) ?? {
        stage,
        label: DELIVERY_FLOW_STAGE_LABELS[stage] ?? stage,
        issueCount: 0,
        storyPoints: 0,
        loggedHours: 0,
        oldestUpdatedDaysAgo: null,
      },
  );
}

function formatDays(value: number | null) {
  if (value == null) return "N/A";
  return `${value}d`;
}

function RoadmapForecastPlanner({
  fiscalYear,
  onError,
  onNotice,
  onPlanChange,
  plan,
  saving,
  setSaving,
  teamRef,
}: {
  fiscalYear: number;
  onError: (message: string | null) => void;
  onNotice: (message: string | null) => void;
  onPlanChange: (plan: TeamRoadmapForecastPlan) => void;
  plan: TeamRoadmapForecastPlan;
  saving: boolean;
  setSaving: (saving: boolean) => void;
  teamRef: string;
}) {
  const [draftHours, setDraftHours] = useState<Record<string, string>>({});
  const [rowMembers, setRowMembers] = useState<Record<string, number[]>>({});
  const [selectedMembers, setSelectedMembers] = useState<Record<string, string>>({});
  const [autosaveState, setAutosaveState] = useState<"idle" | "pending" | "saving" | "saved" | "error">("idle");
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const autosaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const changeVersionRef = useRef(0);
  const savedVersionRef = useRef(0);
  const inFlightVersionRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const queuedSaveRef = useRef(false);
  const draftHoursRef = useRef<Record<string, string>>({});
  const flushPendingAutosaveRef = useRef<() => void>(() => {});
  const rowMembersRef = useRef<Record<string, number[]>>({});
  const productGroupsRef = useRef<PlannerProductGroup[]>([]);
  const productGroups = useMemo(() => groupProductPlannerRows(plan.rows), [plan.rows]);
  const allocationTotal = productGroups.reduce(
    (total, group) => total + groupForecastTotal(group, rowMembers[plannerGroupKey(group)] ?? [], plan.months, draftHours),
    0,
  );
  const actualTotal = productGroups.reduce((total, group) => total + group.actual_hours, 0);
  const scheduledRowCount = productGroups.filter(groupHasPlanningSchedule).length;

  useEffect(() => {
    productGroupsRef.current = productGroups;
  }, [productGroups]);

  useEffect(() => {
    const nextDraft: Record<string, string> = {};
    const nextMembers: Record<string, number[]> = {};
    productGroups.forEach((group) => {
      const rowKey = plannerGroupKey(group);
      const memberIds = new Set<number>();
      const cellTotals = new Map<string, number>();
      group.rows.forEach((row) => {
        row.allocations.forEach((allocation) => {
          memberIds.add(allocation.team_member_id);
          const cellKey = plannerGroupCellKey(group, allocation.team_member_id, allocation.month_sequence);
          cellTotals.set(cellKey, (cellTotals.get(cellKey) ?? 0) + allocation.hours);
        });
      });
      cellTotals.forEach((hours, cellKey) => {
        nextDraft[cellKey] = formatPlannerInput(hours);
      });
      nextMembers[rowKey] = [...memberIds].sort((left, right) => memberName(left, plan.team_members).localeCompare(memberName(right, plan.team_members)));
    });
    draftHoursRef.current = nextDraft;
    rowMembersRef.current = nextMembers;
    savedVersionRef.current = changeVersionRef.current;
    setDraftHours(nextDraft);
    setRowMembers(nextMembers);
    setSelectedMembers({});
  }, [plan.team_members, productGroups]);

  useEffect(() => {
    mountedRef.current = true;
    const flushOnPageExit = () => flushPendingAutosaveRef.current();
    const flushOnVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        flushPendingAutosaveRef.current();
      }
    };

    window.addEventListener("pagehide", flushOnPageExit);
    document.addEventListener("visibilitychange", flushOnVisibilityChange);

    return () => {
      mountedRef.current = false;
      flushPendingAutosaveRef.current();
      window.removeEventListener("pagehide", flushOnPageExit);
      document.removeEventListener("visibilitychange", flushOnVisibilityChange);
    };
  }, []);

  function addMember(group: PlannerProductGroup) {
    const rowKey = plannerGroupKey(group);
    const selectedMemberId = Number(selectedMembers[rowKey]);
    if (!Number.isFinite(selectedMemberId)) return;
    const existing = rowMembersRef.current[rowKey] ?? [];
    if (!existing.includes(selectedMemberId)) {
      const nextMembers = { ...rowMembersRef.current, [rowKey]: [...existing, selectedMemberId] };
      rowMembersRef.current = nextMembers;
      setRowMembers(nextMembers);
    }
    setSelectedMembers((current) => ({ ...current, [rowKey]: "" }));
  }

  function updateCell(group: PlannerProductGroup, memberId: number, monthSequence: number, value: string) {
    const nextDraft = { ...draftHoursRef.current, [plannerGroupCellKey(group, memberId, monthSequence)]: value };
    changeVersionRef.current += 1;
    draftHoursRef.current = nextDraft;
    setDraftHours(nextDraft);
    scheduleAutosave();
  }

  function scheduleAutosave() {
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
    }
    setAutosaveState("pending");
    autosaveTimerRef.current = setTimeout(() => {
      autosaveTimerRef.current = null;
      void savePlannerSnapshot(changeVersionRef.current);
    }, PLANNER_AUTOSAVE_DELAY_MS);
  }

  function flushAutosave() {
    flushPendingAutosave();
  }

  function flushPendingAutosave() {
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    if (changeVersionRef.current === savedVersionRef.current) return;
    void savePlannerSnapshot(changeVersionRef.current);
  }

  flushPendingAutosaveRef.current = flushPendingAutosave;

  async function savePlannerSnapshot(version: number) {
    if (inFlightVersionRef.current !== null) {
      queuedSaveRef.current = true;
      if (mountedRef.current) setAutosaveState("pending");
      return;
    }
    const entries = productPlannerEntries(productGroupsRef.current, rowMembersRef.current, draftHoursRef.current, fiscalYear, plan.months);
    if (!entries.length) {
      if (mountedRef.current) onError(null);
      if (version === changeVersionRef.current) {
        savedVersionRef.current = version;
        if (mountedRef.current) setAutosaveState("saved");
      } else {
        queuedSaveRef.current = true;
        if (mountedRef.current) setAutosaveState("pending");
        requestAnimationFrame(() => void savePlannerSnapshot(changeVersionRef.current));
      }
      return;
    }

    inFlightVersionRef.current = version;
    queuedSaveRef.current = false;
    if (mountedRef.current) {
      setSaving(true);
      setAutosaveState("saving");
      onError(null);
      onNotice(null);
    }
    let shouldSaveLatestAfterFlight = false;
    try {
      const updated = await api.upsertTeamRoadmapForecastPlan(teamRef, fiscalYear, entries);
      if (version === changeVersionRef.current) {
        savedVersionRef.current = version;
        if (mountedRef.current) {
          onPlanChange(updated);
          setLastSavedAt(new Date());
          setAutosaveState("saved");
        }
      } else {
        shouldSaveLatestAfterFlight = true;
        if (mountedRef.current) setAutosaveState("pending");
      }
    } catch (err) {
      if (version === changeVersionRef.current) {
        if (mountedRef.current) {
          setAutosaveState("error");
          onError(err instanceof Error ? err.message : "Unable to autosave Product Forecast");
        }
      } else {
        shouldSaveLatestAfterFlight = true;
        if (mountedRef.current) setAutosaveState("pending");
      }
    } finally {
      if (inFlightVersionRef.current === version) {
        inFlightVersionRef.current = null;
      }
      if (mountedRef.current) setSaving(false);
      if (queuedSaveRef.current || shouldSaveLatestAfterFlight) {
        queuedSaveRef.current = false;
        if (mountedRef.current) setAutosaveState("pending");
        requestAnimationFrame(() => void savePlannerSnapshot(changeVersionRef.current));
      }
    }
  }

  return (
    <section id="product-forecast-planner" className="rounded-lg border bg-card p-4">
      <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-start">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Product Forecast Planner</h2>
          <p className="mt-1 max-w-4xl text-sm text-muted-foreground">
            Enter Product Forecast hours by Team Member and month. Planning signals highlight when each Product is expected to be worked on.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 lg:justify-end">
          <PlannerMetric label="Product Fcst" value={formatHours(allocationTotal)} />
          <PlannerMetric label="Actual" value={formatHours(actualTotal)} />
          <PlannerAutosaveStatus lastSavedAt={lastSavedAt} saving={saving} state={autosaveState} />
        </div>
      </div>

      {plan.rows.length > 0 && scheduledRowCount === 0 ? (
        <div className="mt-3 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-muted-foreground">
          <span className="font-semibold text-primary">No schedule months are synced yet.</span> Run the planning sync after source dates are available, then SPARC will
          shade the matching month columns.
        </div>
      ) : null}

      <div className="mt-4 space-y-3">
        {productGroups.length ? (
          productGroups.map((group) => {
            const groupKey = plannerGroupKey(group);
            const memberIds = rowMembers[groupKey] ?? [];
            const canForecast = group.product_id != null && group.bucket_id != null;
            const availableMembers = plan.team_members.filter((member) => !memberIds.includes(member.id));
            return (
              <div key={group.group_key} className="overflow-hidden rounded-lg border">
                <div className="flex flex-col gap-3 border-b bg-secondary/30 p-3 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {group.product ? (
                        <ProductNameLink className="text-lg font-semibold text-primary hover:underline" productId={group.product_id} productSlug={group.product_slug}>
                          {group.product}
                        </ProductNameLink>
                      ) : (
                        <span className="text-lg font-semibold text-primary">Needs product mapping</span>
                      )}
                      <Badge className="border-primary/30 text-primary">{group.bucket ?? "Needs bucket/category"}</Badge>
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">{group.program_areas.length ? group.program_areas.join(", ") : "Program area not set"}</div>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-end">
                    <div className="flex gap-2">
                      <PlannerMetric label="Forecast" value={formatHours(groupForecastTotal(group, memberIds, plan.months, draftHours))} />
                      <PlannerMetric label="Actual" value={formatHours(group.actual_hours)} />
                      <PlannerMetric label="Tickets" value={String(group.ticket_count)} />
                    </div>
                    <div className="flex gap-2">
                      <select
                        aria-label={`Add Team Member to ${group.product ?? "Product Forecast"}`}
                        className="h-9 min-w-56 rounded-md border border-input bg-background px-3 text-sm"
                        disabled={!canForecast || !availableMembers.length}
                        value={selectedMembers[groupKey] ?? ""}
                        onChange={(event) => setSelectedMembers((current) => ({ ...current, [groupKey]: event.target.value }))}
                      >
                        <option value="">{canForecast ? "Add Team Member" : "Map product and bucket first"}</option>
                        {availableMembers.map((member) => (
                          <option key={member.id} value={member.id}>
                            {member.name}
                          </option>
                        ))}
                      </select>
                      <Button disabled={!canForecast || !selectedMembers[groupKey]} onClick={() => addMember(group)} size="sm" type="button" variant="outline">
                        <Plus className="h-4 w-4" />
                        Add
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="overflow-hidden">
                  <Table className="table-fixed">
                    <colgroup>
                      <col className="w-36 md:w-44" />
                      {plan.months.map((month) => (
                        <col key={month.id} />
                      ))}
                      <col className="w-14 md:w-16" />
                    </colgroup>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="px-2">Team Member</TableHead>
                        {plan.months.map((month) => (
                          <TableHead
                            key={month.id}
                            className={`px-1 text-center text-[11px] ${groupMonthIsActive(group, month) ? "roadmap-schedule-head" : ""}`}
                          >
                            {month.label}
                          </TableHead>
                        ))}
                        <TableHead className="px-1 text-right text-[11px]">Total</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {memberIds.length ? (
                        memberIds.map((memberId) => (
                          <TableRow key={`${groupKey}:${memberId}`}>
                            <TableCell className="truncate px-2 font-medium">
                              <TeamMemberNameLink className="text-primary hover:underline" member={memberForId(memberId, plan.team_members) ?? { id: memberId }}>
                                {memberName(memberId, plan.team_members)}
                              </TeamMemberNameLink>
                            </TableCell>
                            {plan.months.map((month) => {
                              const key = plannerGroupCellKey(group, memberId, month.sequence);
                              const isPlannedMonth = groupMonthIsActive(group, month);
                              return (
                                <TableCell key={month.id} className={`px-1 py-2 ${isPlannedMonth ? "roadmap-schedule-cell" : ""}`}>
                                  <Input
                                    aria-label={`${group.product ?? "Product Forecast"} ${memberName(memberId, plan.team_members)} ${month.label} forecast hours`}
                                    className={`numeric-cell h-8 w-full min-w-0 px-1 text-right text-xs sm:text-sm ${isPlannedMonth ? "roadmap-schedule-input" : ""}`}
                                    disabled={!canForecast}
                                    inputMode="decimal"
                                    pattern="[0-9]*[.]?[0-9]*"
                                    type="text"
                                    value={draftHours[key] ?? ""}
                                    onChange={(event) => updateCell(group, memberId, month.sequence, event.target.value)}
                                    onBlur={flushAutosave}
                                    onKeyDown={(event) => {
                                      if (event.key === "Enter") {
                                        event.currentTarget.blur();
                                      }
                                    }}
                                  />
                                </TableCell>
                              );
                            })}
                            <TableCell className="numeric-cell px-1 text-right text-xs font-semibold sm:text-sm">
                              {formatHours(memberGroupTotal(group, memberId, plan.months, draftHours))}
                            </TableCell>
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell className="py-4 text-muted-foreground" colSpan={plan.months.length + 2}>
                            No Team Members allocated yet.
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              </div>
            );
          })
        ) : (
          <div className="rounded-lg border bg-secondary/20 p-5 text-sm text-muted-foreground">
            No Product Forecast planning targets are assigned to {plan.team} for this fiscal year yet.
          </div>
        )}
      </div>
    </section>
  );
}

function PlannerMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-28 rounded-md bg-secondary/60 px-3 py-2 text-right">
      <div className="text-[10px] font-semibold uppercase text-muted-foreground">{label}</div>
      <div className="numeric-cell text-sm font-semibold text-primary">{value}</div>
    </div>
  );
}

function PlannerAutosaveStatus({
  lastSavedAt,
  saving,
  state,
}: {
  lastSavedAt: Date | null;
  saving: boolean;
  state: "idle" | "pending" | "saving" | "saved" | "error";
}) {
  const label =
    state === "error"
      ? "Save failed"
      : saving || state === "saving"
        ? "Saving"
        : state === "pending"
          ? "Queued"
          : state === "saved"
            ? lastSavedAt
              ? `Saved ${lastSavedAt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`
              : "Saved"
            : "Autosave";
  const tone =
    state === "error"
      ? "border-destructive/40 bg-destructive/10 text-destructive"
      : state === "saved"
        ? "border-[color:var(--spark-cyan)] bg-accent/10 text-primary"
        : "border-border bg-secondary/60 text-muted-foreground";

  return (
    <div className={`flex min-w-32 items-center justify-end gap-2 rounded-md border px-3 py-2 text-sm font-semibold ${tone}`}>
      <Save className="h-4 w-4" />
      <span>{label}</span>
    </div>
  );
}

type PlannerProductGroup = {
  actual_hours: number;
  bucket: string | null;
  bucket_id: number | null;
  forecast_hours: number;
  group_key: string;
  product: string | null;
  product_id: number | null;
  product_slug: string | null;
  program_areas: string[];
  rows: TeamRoadmapForecastRow[];
  ticket_count: number;
};

function groupProductPlannerRows(rows: TeamRoadmapForecastRow[]) {
  const groups = new Map<string, PlannerProductGroup>();
  rows.forEach((row) => {
    const groupKey = `${row.product_id ?? "none"}:${row.bucket_id ?? "none"}`;
    const existing = groups.get(groupKey);
    const group =
      existing ??
      {
        actual_hours: 0,
        bucket: row.bucket,
        bucket_id: row.bucket_id,
        forecast_hours: 0,
        group_key: groupKey,
        product: row.product,
        product_id: row.product_id,
        product_slug: row.product_slug,
        program_areas: [],
        rows: [],
        ticket_count: 0,
      };
    group.rows.push(row);
    group.forecast_hours += row.forecast_hours;
    group.actual_hours += row.actual_hours;
    group.ticket_count += row.ticket_count;
    if (row.program_area && !group.program_areas.includes(row.program_area)) {
      group.program_areas.push(row.program_area);
    }
    groups.set(groupKey, group);
  });
  return [...groups.values()]
    .map((group) => ({
      ...group,
      program_areas: [...group.program_areas].sort((left, right) => left.localeCompare(right)),
      rows: [...group.rows].sort(comparePlanningRows),
    }))
    .sort((left, right) => (left.product ?? "zz").localeCompare(right.product ?? "zz") || (left.bucket ?? "zz").localeCompare(right.bucket ?? "zz"));
}

function comparePlanningRows(left: TeamRoadmapForecastRow, right: TeamRoadmapForecastRow) {
  return (
    (left.roadmap_start_date ?? "").localeCompare(right.roadmap_start_date ?? "") ||
    (left.roadmap_end_date ?? "").localeCompare(right.roadmap_end_date ?? "") ||
    left.roadmap_item_key.localeCompare(right.roadmap_item_key)
  );
}

function plannerGroupKey(group: PlannerProductGroup) {
  return group.group_key;
}

function plannerGroupCellKey(group: PlannerProductGroup, teamMemberId: number, monthSequence: number) {
  return `${plannerGroupKey(group)}:${teamMemberId}:${monthSequence}`;
}

function rowHasPlanningSchedule(row: TeamRoadmapForecastRow) {
  return Boolean(row.roadmap_start_date || row.roadmap_end_date);
}

function groupHasPlanningSchedule(group: PlannerProductGroup) {
  return group.rows.some(rowHasPlanningSchedule);
}

function groupMonthIsActive(group: PlannerProductGroup, month: TeamRoadmapForecastPlan["months"][number]) {
  return group.rows.some((row) => rowMonthIsActive(row, month));
}

function rowMonthIsActive(row: TeamRoadmapForecastRow, month: TeamRoadmapForecastPlan["months"][number]) {
  const start = parseDateOnly(row.roadmap_start_date);
  const end = parseDateOnly(row.roadmap_end_date) ?? start;
  if (!start && !end) return false;
  const first = start ?? end;
  const last = end ?? start;
  if (!first || !last) return false;
  const from = first <= last ? first : last;
  const to = first <= last ? last : first;
  const monthDate = new Date(month.calendar_year, month.calendar_month - 1, 1);
  return monthDate >= new Date(from.getFullYear(), from.getMonth(), 1) && monthDate <= new Date(to.getFullYear(), to.getMonth(), 1);
}

function parseDateOnly(value: string | null | undefined) {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
  return new Date(year, month - 1, day);
}

function memberName(memberId: number, members: TeamMember[]) {
  return memberForId(memberId, members)?.name ?? `Team Member ${memberId}`;
}

function memberForId(memberId: number, members: TeamMember[]) {
  return members.find((member) => member.id === memberId);
}

function formatPlannerInput(value: number) {
  return value > 0 ? String(value) : "";
}

function plannerNumber(value: string | undefined) {
  if (value == null || value.trim() === "") return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

function memberGroupTotal(group: PlannerProductGroup, memberId: number, months: TeamRoadmapForecastPlan["months"], draftHours: Record<string, string>) {
  return months.reduce((total, month) => total + plannerNumber(draftHours[plannerGroupCellKey(group, memberId, month.sequence)]), 0);
}

function groupForecastTotal(
  group: PlannerProductGroup,
  memberIds: number[],
  months: TeamRoadmapForecastPlan["months"],
  draftHours: Record<string, string>,
) {
  return memberIds.reduce((total, memberId) => total + memberGroupTotal(group, memberId, months, draftHours), 0);
}

function productPlannerEntries(
  groups: PlannerProductGroup[],
  rowMembers: Record<string, number[]>,
  draftHours: Record<string, string>,
  fiscalYear: number,
  months: TeamRoadmapForecastPlan["months"],
): RoadmapForecastAllocationUpsertPayload[] {
  const entries: RoadmapForecastAllocationUpsertPayload[] = [];
  groups.forEach((group) => {
    if (group.product_id == null || group.bucket_id == null) return;
    const productId = group.product_id;
    const bucketId = group.bucket_id;
    const memberIds = rowMembers[plannerGroupKey(group)] ?? [];
    memberIds.forEach((teamMemberId) => {
      const memberHasForecastInput = months.some((month) => plannerGroupCellKey(group, teamMemberId, month.sequence) in draftHours);
      if (!memberHasForecastInput) return;
      months.forEach((month) => {
        const row = sourceRowForGroupMonth(group, month);
        if (!row) return;
        const key = plannerGroupCellKey(group, teamMemberId, month.sequence);
        const hours = plannerNumber(draftHours[key]);
        entries.push({
          roadmap_item_id: row.roadmap_item_id,
          product_id: productId,
          team_member_id: teamMemberId,
          bucket_id: bucketId,
          fiscal_year: fiscalYear,
          month_sequence: month.sequence,
          hours,
        });
      });
    });
  });
  return entries;
}

function sourceRowForGroupMonth(group: PlannerProductGroup, month: TeamRoadmapForecastPlan["months"][number]) {
  return group.rows.find((row) => rowMonthIsActive(row, month)) ?? group.rows.find(rowHasPlanningSchedule) ?? group.rows[0] ?? null;
}

function TeamSummaryCards({ analytics }: { analytics: TeamAnalytics }) {
  const primaryProduct = analytics.products[0];
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
      <MetricCard density="compact" label="Active Members" value={formatHours(analytics.activeMembers)} />
      <MetricCard density="compact" label="FYTD Actual Hrs" tone="good" value={formatHours(analytics.actualHours)} />
      <MetricCard density="compact" label="FY Forecast Hrs" value={formatHours(analytics.forecastHours)} />
      <MetricCard density="compact" label="Products Supported" value={formatHours(analytics.productsSupported)} />
      <SummaryTextCard label="Primary Product" to={primaryProduct ? breakdownProductPath(primaryProduct) : undefined} value={analytics.primaryProduct} />
      <SummaryTextCard label="Primary Work Type" value={analytics.primaryWorkType} />
    </section>
  );
}

function SummaryTextCard({ label, value, to }: { label: string; value: string; to?: string }) {
  return (
    <div className="grid min-h-[78px] grid-rows-[1rem_1fr] gap-1 rounded-lg border bg-card p-3">
      <div className="truncate text-[11px] font-semibold uppercase text-muted-foreground" title={label}>
        {label}
      </div>
      <div className="flex min-w-0 items-center text-base font-semibold leading-tight text-primary" title={value}>
        {to ? (
          <Link className="line-clamp-2 hover:underline" to={to}>
            {value}
          </Link>
        ) : (
          <span className="line-clamp-2">{value}</span>
        )}
      </div>
    </div>
  );
}

function TeamMonthlyForecastActualCard({ analytics }: { analytics: TeamAnalytics }) {
  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Monthly Forecast vs Actual</h2>
          <p className="mt-1 text-sm text-muted-foreground">Actuals are FYTD; future months normally show forecast only.</p>
        </div>
        <div className="numeric-cell text-right text-sm text-muted-foreground">
          {formatHours(analytics.actualHours)} actual / {formatHours(analytics.forecastHours)} forecast
        </div>
      </div>
      <div className="mt-4 h-64">
        <ResponsiveContainer height="100%" width="100%">
          <BarChart data={analytics.monthly} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis axisLine={false} dataKey="label" tickLine={false} />
            <YAxis axisLine={false} tickFormatter={(value: number) => formatHours(value)} tickLine={false} width={44} />
            <Tooltip formatter={(value: number, name: string) => [`${formatHours(value)} hrs`, name === "forecastHours" ? "Forecast" : "Actual"]} />
            <Bar dataKey="forecastHours" fill="var(--spark-navy)" radius={[4, 4, 0, 0]} />
            <Bar dataKey="actualHours" fill="var(--spark-cyan)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function TeamBreakdownTable({ rows, title, linkProducts = false }: { rows: TeamAnalyticsBreakdownRow[]; title: string; linkProducts?: boolean }) {
  const maxActual = Math.max(...rows.map((row) => row.actualHours), 0);
  return (
    <section className="overflow-hidden rounded-lg border bg-card">
      <div className="border-b bg-secondary/50 px-4 py-3">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">{title}</h2>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead className="text-right">Actual</TableHead>
            <TableHead className="text-right">Forecast</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length ? (
            rows.slice(0, 8).map((row) => (
              <TableRow key={row.id}>
                <TableCell>
                  <div className="font-medium text-foreground">
                    {linkProducts ? (
                      <Link className="text-primary hover:underline" to={breakdownProductPath(row)}>
                        {row.label}
                      </Link>
                    ) : (
                      row.label
                    )}
                  </div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-secondary">
                    <div
                      className="h-full rounded-full bg-[color:var(--spark-cyan)]"
                      style={{ width: `${maxActual > 0 ? Math.max(4, (row.actualHours / maxActual) * 100) : 0}%` }}
                    />
                  </div>
                </TableCell>
                <TableCell className="numeric-cell text-right font-medium text-primary">{formatHours(row.actualHours)}</TableCell>
                <TableCell className="numeric-cell text-right text-muted-foreground">{formatHours(row.forecastHours)}</TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell className="py-5 text-muted-foreground" colSpan={3}>
                No data yet.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </section>
  );
}

function ProductNameLink({
  children,
  className,
  productId,
  productSlug,
}: {
  children: string;
  className?: string;
  productId?: number | null;
  productSlug?: string | null;
}) {
  if (productId == null && !productSlug) {
    return <span className={className}>{children}</span>;
  }
  return (
    <Link className={className} to={productDetailPath({ product_id: productId ?? undefined, product_slug: productSlug })}>
      {children}
    </Link>
  );
}

function breakdownProductPath(row: TeamAnalyticsBreakdownRow) {
  return productDetailPath({ product_id: typeof row.id === "number" ? row.id : undefined, product_slug: row.product_slug });
}
