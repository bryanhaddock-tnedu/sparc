import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { teamMemberDetailPath } from "../lib/routes";
import { TEAM_RANKING_DIMENSIONS, type TeamMemberRankingRow, type TeamRankingDimension } from "../lib/teamAnalytics";
import { formatBillRate, isContractorEmploymentType, isFteEmploymentType, isVendorEmploymentType } from "../lib/teamMembers";
import { formatCurrency, formatHours } from "../lib/utils";
import { Badge } from "./ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

type EmploymentTypeFilter = "all" | "fte" | "contractor" | "vendor";

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
  const selectedDimension = TEAM_RANKING_DIMENSIONS.find((option) => option.key === dimension)?.label ?? "Rank Value";
  const rankValueDetail = rankingValueDetail(dimension);

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
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm sm:w-36"
              value={employmentTypeFilter}
              onChange={(event) => setEmploymentTypeFilter(event.target.value as EmploymentTypeFilter)}
            >
              <option value="all">All</option>
              <option value="fte">FTE</option>
              <option value="contractor">Contractor</option>
              <option value="vendor">Vendor</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="block text-xs font-semibold uppercase text-muted-foreground">Rank By</span>
            <select
              aria-label={`${title} ranking dimension`}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm sm:w-60"
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
      <div className="overflow-hidden">
        <Table className="w-full table-fixed">
          <colgroup>
            <col className="w-[4%]" />
            <col className={showTeam ? "w-[15%]" : "w-[23%]"} />
            <col className={showTeam ? "w-[10%]" : "w-[12%]"} />
            {showTeam ? <col className="w-[10%]" /> : null}
            <col className="w-[7%]" />
            <col className="w-[11%]" />
            <col className={showTeam ? "w-[12%]" : "w-[13%]"} />
            <col className={showTeam ? "w-[8%]" : "w-[7%]"} />
            <col className={showTeam ? "w-[10%]" : "w-[11%]"} />
            <col className={showTeam ? "w-[8%]" : "w-[6%]"} />
            <col className={showTeam ? "w-[5%]" : "w-[6%]"} />
          </colgroup>
          <TableHeader>
            <TableRow>
              <TableHead className="px-2">Rank</TableHead>
              <TableHead>Team Member</TableHead>
              <TableHead>Role / Type</TableHead>
              {showTeam ? <TableHead>Team</TableHead> : null}
              <TableHead className="text-right">Rate</TableHead>
              <TableHead className="text-right">Annual Cap</TableHead>
              <TableHead className="text-right">Forecast</TableHead>
              <TableHead className="text-right">Coverage</TableHead>
              <TableHead className="text-right">FYTD Actual</TableHead>
              <TableHead className="text-right">Delivery</TableHead>
              <TableHead className="text-right" title={`Ranked by ${selectedDimension}`}>
                <div>Rank Value</div>
                <div className="text-[10px] font-medium text-muted-foreground">{rankValueDetail}</div>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rankedRows.length ? (
              rankedRows.map((row, index) => (
                <TableRow key={row.memberId}>
                  <TableCell className="numeric-cell px-2 text-muted-foreground">{index + 1}</TableCell>
                  <TableCell className="min-w-0">
                    <Link className="block truncate font-medium text-primary hover:underline" title={row.name} to={teamMemberDetailPath(row)}>
                      {row.name}
                    </Link>
                    {row.status !== "active" ? <Badge className="ml-2 border-muted text-muted-foreground">{row.status}</Badge> : null}
                  </TableCell>
                  <TableCell className="min-w-0">
                    <div className="truncate" title={row.role}>
                      {row.role}
                    </div>
                    <Badge className={`mt-1 max-w-full truncate ${employmentBadgeClass(row.employmentType)}`}>{employmentTypeLabel(row.employmentType)}</Badge>
                  </TableCell>
                  {showTeam ? (
                    <TableCell className="truncate" title={row.team}>
                      {row.team}
                    </TableCell>
                  ) : null}
                  <TableCell className="numeric-cell text-right font-medium text-primary">{formatBillRate(row.billRate, row.employmentType)}</TableCell>
                  <TableCell className="numeric-cell text-right">
                    <div className="font-medium">{formatCurrency(row.annualCostCap)}</div>
                    <div className="text-xs text-muted-foreground">{formatHours(row.annualCapacityHours)} hrs</div>
                  </TableCell>
                  <TableCell className="numeric-cell text-right">
                    <div className="font-semibold text-primary">{formatHours(row.fyForecastHours)} hrs</div>
                    <div className="text-xs text-muted-foreground">{formatCurrency(row.fyForecastCost)}</div>
                  </TableCell>
                  <TableCell className="numeric-cell text-right">{formatPercent(row.forecastCapCoveragePercent)}</TableCell>
                  <TableCell className="numeric-cell text-right">
                    <div>{formatHours(row.fytdActualHours)} hrs</div>
                    <div className="text-xs text-muted-foreground">{formatCurrency(row.fytdActualCost)}</div>
                  </TableCell>
                  <TableCell className="numeric-cell text-right">
                    <div>{row.ticketsTouched} tickets</div>
                    <div className="text-xs text-muted-foreground">{formatNullableHours(row.storyPointsPerLoggedHour)} SP/hr</div>
                  </TableCell>
                  <TableCell className="numeric-cell text-right font-semibold text-primary" title={selectedDimension}>
                    {formatRankingValue(row, dimension)}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell className="py-5 text-muted-foreground" colSpan={showTeam ? 11 : 10}>
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
  if (filter === "fte") return isFteEmploymentType(employmentType);
  if (filter === "vendor") return isVendorEmploymentType(employmentType);
  return isContractorEmploymentType(employmentType);
}

function employmentTypeLabel(employmentType: string) {
  if (isFteEmploymentType(employmentType)) return "FTE";
  if (isVendorEmploymentType(employmentType)) return "Vendor";
  if (isContractorEmploymentType(employmentType)) return "Contractor";
  return employmentType || "Unspecified";
}

function employmentBadgeClass(employmentType: string) {
  if (isFteEmploymentType(employmentType)) return "border-primary/40 text-primary";
  if (isVendorEmploymentType(employmentType)) return "border-[color:var(--spark-orange)] text-primary";
  return "border-[color:var(--spark-cyan)] text-primary";
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
  if (dimension === "tickets_touched") return `${value.toLocaleString()} tickets`;
  if (dimension === "products_supported") return `${value.toLocaleString()} products`;
  if (dimension === "story_points") return `${formatHours(value)} SP`;
  if (dimension === "hours_per_ticket") return `${formatHours(value)} hrs/ticket`;
  if (dimension === "hours_per_story_point") return `${formatHours(value)} hrs/SP`;
  if (dimension === "story_points_per_logged_hour") return `${formatHours(value)} SP/hr`;
  return `${formatHours(value)} hrs`;
}

function rankingValueDetail(dimension: TeamRankingDimension) {
  switch (dimension) {
    case "fytd_actual":
      return "FYTD hrs";
    case "current_actual":
      return "Current hrs";
    case "previous_actual":
      return "Previous hrs";
    case "avg_monthly_actual":
      return "Avg/mo";
    case "fy_forecast":
      return "Forecast hrs";
    case "fytd_variance":
      return "Actual - Fcst";
    case "products_supported":
      return "Products";
    case "tickets_touched":
      return "Tickets";
    case "hours_per_ticket":
      return "Hrs/ticket";
    case "story_points":
      return "Story pts";
    case "hours_per_story_point":
      return "Hrs/SP";
    case "story_points_per_logged_hour":
      return "SP/hr";
  }
}

function formatNullableHours(value: number | null) {
  return value == null ? "N/A" : formatHours(value);
}

function formatPercent(value: number | null) {
  return value == null ? "N/A" : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
}
