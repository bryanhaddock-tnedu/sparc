import type { ReportedValueRow, TeamMember, TeamMemberStoryPointMetric } from "../types/api";

export const UNASSIGNED_TEAM = "Unassigned";
export const FISCAL_MONTH_LABELS = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"];

export type TeamRankingPeriod = "current" | "previous" | "fytd";
export type TeamRankingDimension =
  | "fytd_actual"
  | "current_actual"
  | "previous_actual"
  | "avg_monthly_actual"
  | "fy_forecast"
  | "fytd_variance"
  | "products_supported"
  | "tickets_touched"
  | "hours_per_ticket"
  | "story_points"
  | "hours_per_story_point"
  | "story_points_per_logged_hour";

export const TEAM_RANKING_PERIODS: Array<{ key: TeamRankingPeriod; label: string }> = [
  { key: "fytd", label: "FYTD" },
  { key: "current", label: "Current Month" },
  { key: "previous", label: "Previous Month" },
];

export const TEAM_RANKING_DIMENSIONS: Array<{ key: TeamRankingDimension; label: string }> = [
  { key: "fytd_actual", label: "FYTD Actual Hours" },
  { key: "current_actual", label: "Current Month Actual" },
  { key: "previous_actual", label: "Previous Month Actual" },
  { key: "avg_monthly_actual", label: "Avg Hours / Month" },
  { key: "fy_forecast", label: "FY Forecast Hours" },
  { key: "fytd_variance", label: "FYTD Actual - Forecast" },
  { key: "products_supported", label: "Products Supported" },
  { key: "tickets_touched", label: "Tickets Touched" },
  { key: "hours_per_ticket", label: "Hours / Ticket" },
  { key: "story_points", label: "Story Points" },
  { key: "hours_per_story_point", label: "Hours / Story Point" },
  { key: "story_points_per_logged_hour", label: "Story Points / Logged Hour" },
];

export type TeamActualSlice = {
  team: string;
  hours: number;
};

export type TeamActualPeriod = {
  label: string;
  data: TeamActualSlice[];
  total: number;
};

export type TeamActualMonth = {
  label: string;
  hours: number;
};

export type TeamMemberRanking = {
  memberId: number;
  name: string;
  role: string;
  team: string;
  status: string;
  hours: number;
  percentOfTotal: number;
};

export type TeamMemberRankingRow = {
  memberId: number;
  name: string;
  role: string;
  team: string;
  status: string;
  currentActualHours: number;
  previousActualHours: number;
  fytdActualHours: number;
  avgMonthlyActualHours: number;
  fyForecastHours: number;
  fytdForecastHours: number;
  fytdVarianceHours: number;
  productsSupported: number;
  percentOfFytdActual: number;
  ticketsTouched: number;
  storyPoints: number;
  issueLoggedHours: number;
  hoursPerTicket: number | null;
  hoursPerStoryPoint: number | null;
  storyPointsPerLoggedHour: number | null;
};

export type TeamRankingResult = {
  label: string;
  total: number;
  rows: TeamMemberRanking[];
};

export type TeamAnalyticsBreakdownRow = {
  id: number | string;
  label: string;
  forecastHours: number;
  actualHours: number;
  percentOfActual: number;
};

export type TeamMonthlyForecastActual = {
  label: string;
  forecastHours: number;
  actualHours: number;
};

export type TeamMemberContribution = TeamMemberRanking & {
  forecastHours: number;
};

export type TeamAnalytics = {
  team: string;
  members: TeamMember[];
  activeMembers: number;
  forecastHours: number;
  actualHours: number;
  productsSupported: number;
  primaryProduct: string;
  primaryWorkType: string;
  monthly: TeamMonthlyForecastActual[];
  products: TeamAnalyticsBreakdownRow[];
  workTypes: TeamAnalyticsBreakdownRow[];
  roles: TeamAnalyticsBreakdownRow[];
  memberContributions: TeamMemberContribution[];
};

type PeriodRows = Record<TeamRankingPeriod, { label: string; rows: ReportedValueRow[] }>;

export function teamDisplayName(team: string | null | undefined) {
  return team?.trim() || UNASSIGNED_TEAM;
}

export function teamAnalyticsPath(team: string) {
  return `/teams/${encodeURIComponent(teamDisplayName(team))}`;
}

export function buildTeamActualAnalytics(rows: ReportedValueRow[], members: TeamMember[], fiscalYear: number) {
  const teamByMemberId = new Map(members.map((member) => [member.id, teamDisplayName(member.team)]));
  const periods = buildActualPeriodRows(rows, fiscalYear);

  return {
    current: aggregateActualPeriod(periods.current.rows, periods.current.label, teamByMemberId),
    previous: aggregateActualPeriod(periods.previous.rows, periods.previous.label, teamByMemberId),
    fytd: aggregateActualPeriod(periods.fytd.rows, periods.fytd.label, teamByMemberId),
    monthly: aggregateActualMonths(rows),
  };
}

export function buildTeamMemberRankings(rows: ReportedValueRow[], members: TeamMember[], fiscalYear: number): Record<TeamRankingPeriod, TeamRankingResult> {
  const periods = buildActualPeriodRows(rows, fiscalYear);
  return {
    fytd: aggregateMemberRankings(periods.fytd.rows, periods.fytd.label, members),
    current: aggregateMemberRankings(periods.current.rows, periods.current.label, members),
    previous: aggregateMemberRankings(periods.previous.rows, periods.previous.label, members),
  };
}

export function buildTeamMemberRankingRows(
  rows: ReportedValueRow[],
  members: TeamMember[],
  fiscalYear: number,
  storyMetrics: TeamMemberStoryPointMetric[] = [],
  teamName?: string,
): TeamMemberRankingRow[] {
  const team = teamName ? teamDisplayName(teamName).toLowerCase() : null;
  const scopedMembers = team ? members.filter((member) => teamDisplayName(member.team).toLowerCase() === team) : members;
  const scopedMemberIds = new Set(scopedMembers.map((member) => member.id));
  const scopedRows = rows.filter((row) => scopedMemberIds.has(row.team_member_id));
  const storyMetricByMemberId = new Map(storyMetrics.map((metric) => [metric.team_member_id, metric]));
  const periods = buildActualPeriodRows(scopedRows, fiscalYear);
  const currentActualByMemberId = sumHoursByMember(periods.current.rows, "actual_hours");
  const previousActualByMemberId = sumHoursByMember(periods.previous.rows, "actual_hours");
  const fytdActualByMemberId = sumHoursByMember(periods.fytd.rows, "actual_hours");
  const fyForecastByMemberId = sumHoursByMember(scopedRows, "forecast_hours");
  const fytdForecastByMemberId = sumHoursByMember(periods.fytd.rows, "forecast_hours");
  const productIdsByMemberId = new Map<number, Set<number>>();

  for (const row of scopedRows) {
    if (row.actual_hours <= 0 && row.forecast_hours <= 0) continue;
    const products = productIdsByMemberId.get(row.team_member_id) ?? new Set<number>();
    products.add(row.product_id);
    productIdsByMemberId.set(row.team_member_id, products);
  }

  const totalFytdActual = [...fytdActualByMemberId.values()].reduce((sum, hours) => sum + hours, 0);
  const elapsedMonths = fiscalMonthsElapsed(fiscalYear);
  return scopedMembers.map((member) => {
    const fytdActual = fytdActualByMemberId.get(member.id) ?? 0;
    const fytdForecast = fytdForecastByMemberId.get(member.id) ?? 0;
    const storyMetric = storyMetricByMemberId.get(member.id);
    const storyPoints = storyMetric?.story_points ?? 0;
    const issueLoggedHours = storyMetric?.issue_logged_hours ?? 0;
    const ticketsTouched = storyMetric?.issue_count ?? 0;
    return {
      memberId: member.id,
      name: member.name,
      role: member.role,
      team: teamDisplayName(member.team),
      status: member.status,
      currentActualHours: roundHours(currentActualByMemberId.get(member.id) ?? 0),
      previousActualHours: roundHours(previousActualByMemberId.get(member.id) ?? 0),
      fytdActualHours: roundHours(fytdActual),
      avgMonthlyActualHours: elapsedMonths > 0 ? roundHours(fytdActual / elapsedMonths) : 0,
      fyForecastHours: roundHours(fyForecastByMemberId.get(member.id) ?? 0),
      fytdForecastHours: roundHours(fytdForecast),
      fytdVarianceHours: roundHours(fytdActual - fytdForecast),
      productsSupported: productIdsByMemberId.get(member.id)?.size ?? 0,
      percentOfFytdActual: totalFytdActual > 0 ? Math.round((fytdActual / totalFytdActual) * 1000) / 10 : 0,
      ticketsTouched,
      storyPoints: roundHours(storyPoints),
      issueLoggedHours: roundHours(issueLoggedHours),
      hoursPerTicket: ticketsTouched > 0 ? roundHours(issueLoggedHours / ticketsTouched) : null,
      hoursPerStoryPoint: storyPoints > 0 ? roundHours(issueLoggedHours / storyPoints) : null,
      storyPointsPerLoggedHour: issueLoggedHours > 0 ? Math.round((storyPoints / issueLoggedHours) * 100) / 100 : null,
    };
  });
}

export function buildSingleTeamAnalytics(teamName: string, members: TeamMember[], rows: ReportedValueRow[], fiscalYear: number): TeamAnalytics {
  const team = teamDisplayName(teamName);
  const teamMembers = members
    .filter((member) => teamDisplayName(member.team).toLowerCase() === team.toLowerCase())
    .sort((left, right) => left.name.localeCompare(right.name));
  const memberById = new Map(teamMembers.map((member) => [member.id, member]));
  const memberIds = new Set(teamMembers.map((member) => member.id));
  const teamRows = rows.filter((row) => memberIds.has(row.team_member_id));
  const fytdRows = buildActualPeriodRows(teamRows, fiscalYear).fytd.rows;
  const actualHours = roundHours(sumRows(fytdRows, "actual_hours"));
  const forecastHours = roundHours(sumRows(teamRows, "forecast_hours"));
  const productRows = aggregateBreakdown(teamRows, fytdRows, (row) => row.product_id, (row) => row.product);
  const workTypeRows = aggregateBreakdown(teamRows, fytdRows, (row) => row.bucket_id, (row) => row.bucket);
  const roleRows = aggregateRoleBreakdown(teamRows, fytdRows, memberById);

  return {
    team,
    members: teamMembers,
    activeMembers: teamMembers.filter((member) => member.status === "active").length,
    forecastHours,
    actualHours,
    productsSupported: productRows.filter((row) => row.actualHours > 0 || row.forecastHours > 0).length,
    primaryProduct: productRows[0]?.label ?? "None yet",
    primaryWorkType: workTypeRows[0]?.label ?? "None yet",
    monthly: aggregateForecastActualMonths(teamRows),
    products: productRows,
    workTypes: workTypeRows,
    roles: roleRows,
    memberContributions: aggregateTeamMemberContributions(teamMembers, teamRows, fytdRows),
  };
}

function buildActualPeriodRows(rows: ReportedValueRow[], fiscalYear: number): PeriodRows {
  const today = new Date();
  const current = { year: today.getFullYear(), month: today.getMonth() + 1 };
  const previousDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
  const previous = { year: previousDate.getFullYear(), month: previousDate.getMonth() + 1 };
  const currentFiscalYear = current.month >= 7 ? current.year + 1 : current.year;
  const fytdRows =
    fiscalYear < currentFiscalYear
      ? rows
      : fiscalYear > currentFiscalYear
        ? []
        : rows.filter((row) => row.month_sequence <= fiscalSequenceForCalendarMonth(current.month));

  return {
    current: {
      label: monthLabel(current.month),
      rows: rows.filter((row) => row.calendar_year === current.year && row.calendar_month === current.month),
    },
    previous: {
      label: monthLabel(previous.month),
      rows: rows.filter((row) => row.calendar_year === previous.year && row.calendar_month === previous.month),
    },
    fytd: { label: "FYTD", rows: fytdRows },
  };
}

function aggregateActualPeriod(rows: ReportedValueRow[], label: string, teamByMemberId: Map<number, string>): TeamActualPeriod {
  const hoursByTeam = new Map<string, number>();
  for (const row of rows) {
    const team = teamByMemberId.get(row.team_member_id) ?? UNASSIGNED_TEAM;
    hoursByTeam.set(team, (hoursByTeam.get(team) ?? 0) + row.actual_hours);
  }
  const data = Array.from(hoursByTeam, ([team, hours]) => ({ team, hours: roundHours(hours) }))
    .filter((row) => row.hours > 0)
    .sort((left, right) => right.hours - left.hours || left.team.localeCompare(right.team));
  return {
    label,
    data,
    total: roundHours(data.reduce((sum, row) => sum + row.hours, 0)),
  };
}

function aggregateMemberRankings(rows: ReportedValueRow[], label: string, members: TeamMember[]): TeamRankingResult {
  const memberById = new Map(members.map((member) => [member.id, member]));
  const hoursByMemberId = new Map<number, number>();
  for (const row of rows) {
    hoursByMemberId.set(row.team_member_id, (hoursByMemberId.get(row.team_member_id) ?? 0) + row.actual_hours);
  }
  const total = roundHours([...hoursByMemberId.values()].reduce((sum, hours) => sum + hours, 0));
  const ranked = [...hoursByMemberId.entries()]
    .map(([memberId, hours]) => {
      const member = memberById.get(memberId);
      return member
        ? {
            memberId,
            name: member.name,
            role: member.role,
            team: teamDisplayName(member.team),
            status: member.status,
            hours: roundHours(hours),
            percentOfTotal: total > 0 ? Math.round((hours / total) * 1000) / 10 : 0,
          }
        : null;
    })
    .filter((row): row is TeamMemberRanking => row !== null && row.hours > 0)
    .sort((left, right) => right.hours - left.hours || left.name.localeCompare(right.name));
  return { label, total, rows: ranked };
}

function aggregateActualMonths(rows: ReportedValueRow[]): TeamActualMonth[] {
  const hoursBySequence = new Map<number, number>();
  for (const row of rows) {
    hoursBySequence.set(row.month_sequence, (hoursBySequence.get(row.month_sequence) ?? 0) + row.actual_hours);
  }
  return FISCAL_MONTH_LABELS.map((label, index) => ({
    label,
    hours: roundHours(hoursBySequence.get(index + 1) ?? 0),
  }));
}

function aggregateForecastActualMonths(rows: ReportedValueRow[]): TeamMonthlyForecastActual[] {
  const totalsBySequence = new Map<number, { forecastHours: number; actualHours: number }>();
  for (const row of rows) {
    const totals = totalsBySequence.get(row.month_sequence) ?? { forecastHours: 0, actualHours: 0 };
    totals.forecastHours += row.forecast_hours;
    totals.actualHours += row.actual_hours;
    totalsBySequence.set(row.month_sequence, totals);
  }
  return FISCAL_MONTH_LABELS.map((label, index) => {
    const totals = totalsBySequence.get(index + 1);
    return {
      label,
      forecastHours: roundHours(totals?.forecastHours ?? 0),
      actualHours: roundHours(totals?.actualHours ?? 0),
    };
  });
}

function aggregateBreakdown(
  forecastRows: ReportedValueRow[],
  actualRows: ReportedValueRow[],
  idForRow: (row: ReportedValueRow) => number | string,
  labelForRow: (row: ReportedValueRow) => string,
): TeamAnalyticsBreakdownRow[] {
  const rowsById = new Map<number | string, TeamAnalyticsBreakdownRow>();
  for (const row of forecastRows) {
    const id = idForRow(row);
    const existing = rowsById.get(id) ?? { id, label: labelForRow(row), forecastHours: 0, actualHours: 0, percentOfActual: 0 };
    existing.forecastHours += row.forecast_hours;
    rowsById.set(id, existing);
  }
  for (const row of actualRows) {
    const id = idForRow(row);
    const existing = rowsById.get(id) ?? { id, label: labelForRow(row), forecastHours: 0, actualHours: 0, percentOfActual: 0 };
    existing.actualHours += row.actual_hours;
    rowsById.set(id, existing);
  }
  return finalizeBreakdownRows([...rowsById.values()]);
}

function aggregateRoleBreakdown(
  forecastRows: ReportedValueRow[],
  actualRows: ReportedValueRow[],
  memberById: Map<number, TeamMember>,
): TeamAnalyticsBreakdownRow[] {
  return aggregateBreakdown(
    forecastRows,
    actualRows,
    (row) => memberById.get(row.team_member_id)?.role || "Unassigned",
    (row) => memberById.get(row.team_member_id)?.role || "Unassigned",
  );
}

function aggregateTeamMemberContributions(
  members: TeamMember[],
  forecastRows: ReportedValueRow[],
  actualRows: ReportedValueRow[],
): TeamMemberContribution[] {
  const actualByMemberId = new Map<number, number>();
  const forecastByMemberId = new Map<number, number>();
  for (const row of forecastRows) {
    forecastByMemberId.set(row.team_member_id, (forecastByMemberId.get(row.team_member_id) ?? 0) + row.forecast_hours);
  }
  for (const row of actualRows) {
    actualByMemberId.set(row.team_member_id, (actualByMemberId.get(row.team_member_id) ?? 0) + row.actual_hours);
  }
  const totalActual = [...actualByMemberId.values()].reduce((sum, hours) => sum + hours, 0);
  return members
    .map((member) => {
      const actualHours = actualByMemberId.get(member.id) ?? 0;
      return {
        memberId: member.id,
        name: member.name,
        role: member.role,
        team: teamDisplayName(member.team),
        status: member.status,
        hours: roundHours(actualHours),
        forecastHours: roundHours(forecastByMemberId.get(member.id) ?? 0),
        percentOfTotal: totalActual > 0 ? Math.round((actualHours / totalActual) * 1000) / 10 : 0,
      };
    })
    .sort((left, right) => right.hours - left.hours || left.name.localeCompare(right.name));
}

function finalizeBreakdownRows(rows: TeamAnalyticsBreakdownRow[]) {
  const totalActual = rows.reduce((sum, row) => sum + row.actualHours, 0);
  return rows
    .map((row) => ({
      ...row,
      forecastHours: roundHours(row.forecastHours),
      actualHours: roundHours(row.actualHours),
      percentOfActual: totalActual > 0 ? Math.round((row.actualHours / totalActual) * 1000) / 10 : 0,
    }))
    .filter((row) => row.forecastHours > 0 || row.actualHours > 0)
    .sort((left, right) => right.actualHours - left.actualHours || right.forecastHours - left.forecastHours || left.label.localeCompare(right.label));
}

function sumRows(rows: ReportedValueRow[], field: "actual_hours" | "forecast_hours") {
  return rows.reduce((sum, row) => sum + row[field], 0);
}

function sumHoursByMember(rows: ReportedValueRow[], field: "actual_hours" | "forecast_hours") {
  const hoursByMemberId = new Map<number, number>();
  for (const row of rows) {
    hoursByMemberId.set(row.team_member_id, (hoursByMemberId.get(row.team_member_id) ?? 0) + row[field]);
  }
  return hoursByMemberId;
}

function fiscalSequenceForCalendarMonth(calendarMonth: number) {
  return calendarMonth >= 7 ? calendarMonth - 6 : calendarMonth + 6;
}

function fiscalMonthsElapsed(fiscalYear: number) {
  const today = new Date();
  const currentFiscalYear = today.getMonth() + 1 >= 7 ? today.getFullYear() + 1 : today.getFullYear();
  if (fiscalYear < currentFiscalYear) {
    return 12;
  }
  if (fiscalYear > currentFiscalYear) {
    return 0;
  }
  return fiscalSequenceForCalendarMonth(today.getMonth() + 1);
}

function monthLabel(calendarMonth: number) {
  return new Intl.DateTimeFormat(undefined, { month: "short" }).format(new Date(2026, calendarMonth - 1, 1));
}

function roundHours(value: number) {
  return Math.round(value * 10) / 10;
}
