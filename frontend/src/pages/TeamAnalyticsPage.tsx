import { ArrowLeft } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { MetricCard } from "../components/MetricCard";
import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { TeamMemberRankingsTable } from "../components/TeamMemberRankingsTable";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import {
  buildSingleTeamAnalytics,
  buildTeamMemberRankingRows,
  teamDisplayName,
  type TeamAnalytics,
  type TeamAnalyticsBreakdownRow,
  type TeamRankingDimension,
} from "../lib/teamAnalytics";
import { formatHours } from "../lib/utils";
import type { ReportedValueRow, TeamMember, TeamMemberStoryPointMetric } from "../types/api";

export function TeamAnalyticsPage() {
  const params = useParams();
  const teamName = teamDisplayName(safeDecodeURIComponent(params.teamName ?? ""));
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [reportedRows, setReportedRows] = useState<ReportedValueRow[]>([]);
  const [storyMetrics, setStoryMetrics] = useState<TeamMemberStoryPointMetric[]>([]);
  const [rankingDimension, setRankingDimension] = useState<TeamRankingDimension>("fytd_actual");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([api.teamMembers(), api.reportedValues({}, fiscalYear), api.teamMemberStoryPointMetrics(fiscalYear)])
      .then(([memberRows, reportedValueRows, storyPointRows]) => {
        setMembers(memberRows);
        setReportedRows(reportedValueRows);
        setStoryMetrics(storyPointRows);
        setError(null);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load team analytics"))
      .finally(() => setLoading(false));
  }, [fiscalYear]);

  const analytics = useMemo(() => buildSingleTeamAnalytics(teamName, members, reportedRows, fiscalYear), [fiscalYear, members, reportedRows, teamName]);
  const rankingRows = useMemo(
    () => buildTeamMemberRankingRows(reportedRows, members, fiscalYear, storyMetrics, teamName),
    [fiscalYear, members, reportedRows, storyMetrics, teamName],
  );

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
          <TeamSummaryCards analytics={analytics} />
          <TeamMonthlyForecastActualCard analytics={analytics} />
          <TeamMemberRankingsTable
            description={`${analytics.team} members ranked by the selected hours, ticket, or story point signal.`}
            dimension={rankingDimension}
            onDimensionChange={setRankingDimension}
            rows={rankingRows}
            showTeam={false}
            title="Team Member Rankings"
          />
          <div className="grid gap-4 xl:grid-cols-3">
            <TeamBreakdownTable rows={analytics.products} title="Product Mix" />
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

function TeamSummaryCards({ analytics }: { analytics: TeamAnalytics }) {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
      <MetricCard density="compact" label="Active Members" value={formatHours(analytics.activeMembers)} />
      <MetricCard density="compact" label="FYTD Actual Hrs" tone="good" value={formatHours(analytics.actualHours)} />
      <MetricCard density="compact" label="FY Forecast Hrs" value={formatHours(analytics.forecastHours)} />
      <MetricCard density="compact" label="Products Supported" value={formatHours(analytics.productsSupported)} />
      <SummaryTextCard label="Primary Product" value={analytics.primaryProduct} />
      <SummaryTextCard label="Primary Work Type" value={analytics.primaryWorkType} />
    </section>
  );
}

function SummaryTextCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-h-[78px] grid-rows-[1rem_1fr] gap-1 rounded-lg border bg-card p-3">
      <div className="truncate text-[11px] font-semibold uppercase text-muted-foreground" title={label}>
        {label}
      </div>
      <div className="flex min-w-0 items-center text-base font-semibold leading-tight text-primary" title={value}>
        <span className="line-clamp-2">{value}</span>
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

function TeamBreakdownTable({ rows, title }: { rows: TeamAnalyticsBreakdownRow[]; title: string }) {
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
                  <div className="font-medium text-foreground">{row.label}</div>
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
