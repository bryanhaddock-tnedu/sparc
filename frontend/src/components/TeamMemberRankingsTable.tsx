import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { teamMemberDetailPath } from "../lib/routes";
import { TEAM_RANKING_DIMENSIONS, type TeamMemberRankingRow, type TeamRankingDimension } from "../lib/teamAnalytics";
import { formatBillRate, isFteEmploymentType } from "../lib/teamMembers";
import { formatCurrency, formatHours } from "../lib/utils";
import { Badge } from "./ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

type EmploymentTypeFilter = "all" | "fte" | "contractor";

type TeamMemberRankingsTableProps = {
  description?: string;
  dimension: TeamRankingDimension;
  emptyMessage?: string;
  onDimensionChange: (dimension: TeamRankingDimension) => void;
  rows: TeamMemberRankingRow[];
  showTeam?: boolean;
  title: string;
};

export function TeamMemberRankingsTable({
  description,
  dimension,
  emptyMessage = "No ranking data available yet.",
  onDimensionChange,
  rows,
  showTeam = true,
  title,
}: TeamMemberRankingsTableProps) {
  const [employmentTypeFilter, setEmploymentTypeFilter] = useState<EmploymentTypeFilter>("all");
  const filteredRows = useMemo(
    () => rows.filter((row) => employmentTypeMatchesFilter(row.employmentType, employmentTypeFilter)),
    [employmentTypeFilter, rows],
  );
  const rankedRows = useMemo(
    () => [...filteredRows].sort((left, right) => compareRankingRows(left, right, dimension)),
    [dimension, filteredRows],
  );
  const selectedDimension = TEAM_RANKING_DIMENSIONS.find((option) => option.key === dimension)?.label ?? "Metric";

  return (
    <section className="overflow-hidden rounded-lg border bg-card">
      <div className="flex flex-col justify-between gap-3 border-b bg-secondary/50 px-4 py-3 md:flex-row md:items-start">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">{title}</h2>
          {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
          <p className="mt-1 text-xs text-muted-foreground">
            Showing {rankedRows.length} of {rows.length} rostered Team Members.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="space-y-1">
            <span className="block text-xs font-semibold uppercase text-muted-foreground">Employment Type</span>
            <select
              aria-label={`${title} employment type filter`}
              className="h-9 min-w-40 rounded-md border border-input bg-background px-3 text-sm"
              value={employmentTypeFilter}
              onChange={(event) => setEmploymentTypeFilter(event.target.value as EmploymentTypeFilter)}
            >
              <option value="all">All</option>
              <option value="fte">FTE</option>
              <option value="contractor">Contractor</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="block text-xs font-semibold uppercase text-muted-foreground">Rank By</span>
            <select
              aria-label={`${title} ranking dimension`}
              className="h-9 min-w-60 rounded-md border border-input bg-background px-3 text-sm"
              value={dimension}
              onChange={(event) => onDimensionChange(event.target.value as TeamRankingDimension)}
            >
              {TEAM_RANKING_DIMENSIONS.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <div className="overflow-x-auto">
        <Table className="min-w-[1600px]">
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">Rank</TableHead>
              <TableHead>Team Member</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Employment Type</TableHead>
              {showTeam ? <TableHead>Team</TableHead> : null}
              <TableHead className="text-right">Bill Rate</TableHead>
              <TableHead className="text-right">Annual Hrs</TableHead>
              <TableHead className="text-right">Annual Cap</TableHead>
              <TableHead className="text-right">FY Forecast Hrs</TableHead>
              <TableHead className="text-right">Forecast $</TableHead>
              <TableHead className="text-right">Cap Coverage</TableHead>
              <TableHead className="text-right">FYTD Actual Hrs</TableHead>
              <TableHead className="text-right">FYTD Actual $</TableHead>
              <TableHead className="text-right">Tickets</TableHead>
              <TableHead className="text-right">SP / Hr</TableHead>
              <TableHead className="text-right">Rank Metric</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rankedRows.length ? (
              rankedRows.map((row, index) => (
                <TableRow key={row.memberId}>
                  <TableCell className="numeric-cell text-muted-foreground">{index + 1}</TableCell>
                  <TableCell>
                    <Link className="font-medium text-primary hover:underline" to={teamMemberDetailPath(row)}>
                      {row.name}
                    </Link>
                    {row.status !== "active" ? <Badge className="ml-2 border-muted text-muted-foreground">{row.status}</Badge> : null}
                  </TableCell>
                  <TableCell>{row.role}</TableCell>
                  <TableCell>
                    <Badge className={employmentBadgeClass(row.employmentType)}>{employmentTypeLabel(row.employmentType)}</Badge>
                  </TableCell>
                  {showTeam ? <TableCell>{row.team}</TableCell> : null}
                  <TableCell className="numeric-cell text-right font-medium text-primary">{formatBillRate(row.billRate, row.employmentType, { includeUnit: true })}</TableCell>
                  <TableCell className="numeric-cell text-right">{formatHours(row.annualCapacityHours)}</TableCell>
                  <TableCell className="numeric-cell text-right font-medium">{formatCurrency(row.annualCostCap)}</TableCell>
                  <TableCell className="numeric-cell text-right font-semibold text-primary">{formatHours(row.fyForecastHours)}</TableCell>
                  <TableCell className="numeric-cell text-right font-medium text-primary">{formatCurrency(row.fyForecastCost)}</TableCell>
                  <TableCell className="numeric-cell text-right">{formatPercent(row.forecastCapCoveragePercent)}</TableCell>
                  <TableCell className="numeric-cell text-right">{formatHours(row.fytdActualHours)}</TableCell>
                  <TableCell className="numeric-cell text-right">{formatCurrency(row.fytdActualCost)}</TableCell>
                  <TableCell className="numeric-cell text-right">{row.ticketsTouched}</TableCell>
                  <TableCell className="numeric-cell text-right">{formatNullableHours(row.storyPointsPerLoggedHour)}</TableCell>
                  <TableCell className="numeric-cell text-right font-semibold text-primary" title={selectedDimension}>
                    {formatRankingValue(row, dimension)}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell className="py-5 text-muted-foreground" colSpan={showTeam ? 16 : 15}>
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

function employmentTypeMatchesFilter(employmentType: string, filter: EmploymentTypeFilter) {
  if (filter === "all") return true;
  const isFte = isFteEmploymentType(employmentType);
  return filter === "fte" ? isFte : !isFte;
}

function employmentTypeLabel(employmentType: string) {
  return isFteEmploymentType(employmentType) ? "FTE" : "Contractor";
}

function employmentBadgeClass(employmentType: string) {
  return isFteEmploymentType(employmentType) ? "border-primary/40 text-primary" : "border-[color:var(--spark-cyan)] text-primary";
}

function compareRankingRows(left: TeamMemberRankingRow, right: TeamMemberRankingRow, dimension: TeamRankingDimension) {
  const leftValue = rankingNumericValue(left, dimension);
  const rightValue = rankingNumericValue(right, dimension);
  if (leftValue == null && rightValue != null) return 1;
  if (rightValue == null && leftValue != null) return -1;
  if (leftValue != null && rightValue != null && rightValue !== leftValue) return rightValue - leftValue;
  return left.name.localeCompare(right.name);
}

function rankingNumericValue(row: TeamMemberRankingRow, dimension: TeamRankingDimension) {
  switch (dimension) {
    case "fytd_actual":
      return row.fytdActualHours;
    case "current_actual":
      return row.currentActualHours;
    case "previous_actual":
      return row.previousActualHours;
    case "avg_monthly_actual":
      return row.avgMonthlyActualHours;
    case "fy_forecast":
      return row.fyForecastHours;
    case "fytd_variance":
      return row.fytdVarianceHours;
    case "products_supported":
      return row.productsSupported;
    case "tickets_touched":
      return row.ticketsTouched;
    case "hours_per_ticket":
      return row.hoursPerTicket;
    case "story_points":
      return row.storyPoints;
    case "hours_per_story_point":
      return row.hoursPerStoryPoint;
    case "story_points_per_logged_hour":
      return row.storyPointsPerLoggedHour;
  }
}

function formatRankingValue(row: TeamMemberRankingRow, dimension: TeamRankingDimension) {
  const value = rankingNumericValue(row, dimension);
  if (value == null) return "N/A";
  if (dimension === "tickets_touched" || dimension === "products_supported") return String(value);
  return formatHours(value);
}

function formatNullableHours(value: number | null) {
  return value == null ? "N/A" : formatHours(value);
}

function formatPercent(value: number | null) {
  return value == null ? "N/A" : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
}
