import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import { formatBillRate } from "../lib/teamMembers";
import { formatHours } from "../lib/utils";
import type { ReportedValueRow, TeamMember } from "../types/api";

const PIE_COLORS = [
  "var(--spark-cyan)",
  "var(--spark-orange)",
  "var(--spark-navy)",
  "var(--spark-red)",
  "#8fb3d9",
  "#d6d94f",
  "#7a86a8",
  "#f2a65a",
];

export function TeamManagementPage() {
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [reportedRows, setReportedRows] = useState<ReportedValueRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTeamOverview = useCallback(async () => {
    const [memberRows, reportedValueRows] = await Promise.all([api.teamMembers(), api.reportedValues({}, fiscalYear)]);
    setMembers(memberRows);
    setReportedRows(reportedValueRows);
  }, [fiscalYear]);

  useEffect(() => {
    setLoading(true);
    loadTeamOverview()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load team"))
      .finally(() => setLoading(false));
  }, [loadTeamOverview]);

  const updateBillRate = useCallback(async (member: TeamMember, billRate: number) => {
    const updated = await api.updateTeamMember(member.id, { bill_rate: billRate });
    setMembers((current) => current.map((row) => (row.id === member.id ? updated : row)));
  }, []);

  const analytics = useMemo(() => buildTeamReportedAnalytics(reportedRows, fiscalYear), [reportedRows, fiscalYear]);

  const columns = useMemo<ColumnDef<TeamMember>[]>(
    () => [
      {
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => (
          <Link className="font-medium text-primary hover:underline" to={`/team-members/${row.original.id}`}>
            {row.original.name}
          </Link>
        ),
      },
      { accessorKey: "role", header: "Role" },
      { accessorKey: "team", header: "Team" },
      {
        accessorKey: "bill_rate",
        header: "Bill Rate",
        cell: ({ row }) => <BillRateInput member={row.original} onSave={updateBillRate} />,
      },
      { accessorKey: "employment_type", header: "Employment Type" },
      {
        accessorKey: "contracting_company",
        header: "Contracting Company",
        cell: ({ row }) => row.original.contracting_company ?? "",
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => (
          <Badge className={row.original.status === "active" ? "border-primary/40 text-primary" : "border-muted text-muted-foreground"}>
            {row.original.status}
          </Badge>
        ),
      },
      {
        accessorKey: "updated_at",
        header: "Last Updated",
        cell: ({ row }) => formatDate(row.original.updated_at),
      },
    ],
    [updateBillRate],
  );

  const table = useReactTable({ data: members, columns, getCoreRowModel: getCoreRowModel() });

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;

  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold">Team Management</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {members.length} rostered team members / {fiscalYearLabel} ({fiscalYearRangeLabel})
          </p>
        </div>
        <PageNav current="team" />
      </div>

      <section className="overflow-x-auto pb-1">
        <div className="grid min-w-[1080px] grid-cols-3 gap-4">
          <TeamReportedPieCard title={`Previous Month (${analytics.previous.label})`} data={analytics.previous.data} total={analytics.previous.total} />
          <TeamReportedPieCard title={`Current Month (${analytics.current.label})`} data={analytics.current.data} total={analytics.current.total} />
          <TeamReportedPieCard title={`${fiscalYearLabel} FYTD`} data={analytics.fytd.data} total={analytics.fytd.total} />
        </div>
      </section>

      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id}>
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}

function TeamReportedPieCard({ title, data, total }: { title: string; data: TeamReportedSlice[]; total: number }) {
  const hasData = data.some((row) => row.hours > 0);
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">{title}</h2>
          <div className="numeric-cell mt-1 text-2xl font-semibold text-primary">{formatHours(total)}</div>
        </div>
        <div className="text-right text-xs text-muted-foreground">{hasData ? `${data.length} reporting` : "No reported hours"}</div>
      </div>
      <div className="relative mt-2 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={hasData ? data : [{ teamMember: "No reported hours", hours: 1 }]}
              dataKey="hours"
              innerRadius={52}
              nameKey="teamMember"
              outerRadius={108}
              paddingAngle={hasData ? 2 : 0}
            >
              {(hasData ? data : [{ teamMember: "No reported hours", hours: 1 }]).map((entry, index) => (
                <Cell key={entry.teamMember} fill={hasData ? PIE_COLORS[index % PIE_COLORS.length] : "hsl(var(--muted))"} />
              ))}
            </Pie>
            {hasData ? <Tooltip formatter={(value: number, name: string) => [`${formatHours(value)} hrs`, name]} /> : null}
          </PieChart>
        </ResponsiveContainer>
        {!hasData ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-center text-sm font-medium text-muted-foreground">
            No reported hours
          </div>
        ) : null}
      </div>
    </div>
  );
}

function BillRateInput({ member, onSave }: { member: TeamMember; onSave: (member: TeamMember, billRate: number) => Promise<void> }) {
  const [value, setValue] = useState(member.bill_rate > 0 ? String(member.bill_rate) : "");
  const [saving, setSaving] = useState(false);

  useEffect(() => setValue(member.bill_rate > 0 ? String(member.bill_rate) : ""), [member.bill_rate]);

  async function commit() {
    const nextValue = value.trim() === "" ? 0 : Number(value);
    if (!Number.isFinite(nextValue) || nextValue < 0 || nextValue === member.bill_rate) return;
    setSaving(true);
    try {
      await onSave(member, nextValue);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="w-28">
      <Input
        aria-label={`${member.name} bill rate`}
        className="numeric-cell h-8"
        disabled={saving}
        inputMode="decimal"
        pattern="[0-9]*"
        placeholder="Not set"
        type="text"
        value={value}
        onBlur={commit}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
        }}
      />
      <div className="numeric-cell mt-1 text-xs text-muted-foreground">{formatBillRate(member.bill_rate, member.employment_type)}</div>
    </div>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

type TeamReportedSlice = {
  teamMember: string;
  hours: number;
};

type TeamReportedPeriod = {
  label: string;
  data: TeamReportedSlice[];
  total: number;
};

function buildTeamReportedAnalytics(rows: ReportedValueRow[], fiscalYear: number) {
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
    current: aggregateReportedPeriod(
      rows.filter((row) => row.calendar_year === current.year && row.calendar_month === current.month),
      monthLabel(current.month),
    ),
    previous: aggregateReportedPeriod(
      rows.filter((row) => row.calendar_year === previous.year && row.calendar_month === previous.month),
      monthLabel(previous.month),
    ),
    fytd: aggregateReportedPeriod(fytdRows, "FYTD"),
  };
}

function aggregateReportedPeriod(rows: ReportedValueRow[], label: string): TeamReportedPeriod {
  const hoursByMember = new Map<string, number>();
  for (const row of rows) {
    hoursByMember.set(row.team_member, (hoursByMember.get(row.team_member) ?? 0) + row.reported_hours);
  }
  const data = Array.from(hoursByMember, ([teamMember, hours]) => ({ teamMember, hours: roundHours(hours) }))
    .filter((row) => row.hours > 0)
    .sort((left, right) => right.hours - left.hours || left.teamMember.localeCompare(right.teamMember));
  return {
    label,
    data,
    total: roundHours(data.reduce((sum, row) => sum + row.hours, 0)),
  };
}

function fiscalSequenceForCalendarMonth(calendarMonth: number) {
  return calendarMonth >= 7 ? calendarMonth - 6 : calendarMonth + 6;
}

function monthLabel(calendarMonth: number) {
  return new Intl.DateTimeFormat(undefined, { month: "short" }).format(new Date(2026, calendarMonth - 1, 1));
}

function roundHours(value: number) {
  return Math.round(value * 10) / 10;
}
