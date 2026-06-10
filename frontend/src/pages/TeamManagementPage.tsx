import { Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import { formatBillRate } from "../lib/teamMembers";
import { formatHours } from "../lib/utils";
import type { ReportedValueRow, TeamMember, TeamMemberCreatePayload } from "../types/api";

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

type NewTeamMemberForm = {
  staffId: string;
  name: string;
  role: string;
  team: string;
  billRate: string;
  employmentType: string;
  contractingCompany: string;
  status: string;
};

export function TeamManagementPage() {
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [reportedRows, setReportedRows] = useState<ReportedValueRow[]>([]);
  const [newMember, setNewMember] = useState<NewTeamMemberForm>(() => blankTeamMemberForm());
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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

  const createTeamMember = useCallback(async () => {
    const payload = teamMemberPayload(newMember);
    if (typeof payload === "string") {
      setActionError(payload);
      setNotice(null);
      return;
    }

    setCreating(true);
    setActionError(null);
    setNotice(null);
    try {
      const created = await api.createTeamMember(payload);
      await loadTeamOverview();
      setNewMember(blankTeamMemberForm());
      setNotice(`${created.name} was added to the SPARC roster.`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to add team member");
    } finally {
      setCreating(false);
    }
  }, [loadTeamOverview, newMember]);

  const analytics = useMemo(() => buildTeamActualAnalytics(reportedRows, fiscalYear), [reportedRows, fiscalYear]);

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

      {notice ? <div className="rounded-md border border-[color:var(--spark-cyan)] bg-accent/10 px-3 py-2 text-sm text-primary">{notice}</div> : null}
      {actionError ? <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{actionError}</div> : null}

      <section className="overflow-x-auto pb-1">
        <div className="grid min-w-[1080px] grid-cols-3 gap-4">
          <TeamActualPieCard title={`Previous Month (${analytics.previous.label})`} data={analytics.previous.data} total={analytics.previous.total} />
          <TeamActualPieCard title={`Current Month (${analytics.current.label})`} data={analytics.current.data} total={analytics.current.total} />
          <TeamActualPieCard title={`${fiscalYearLabel} FYTD`} data={analytics.fytd.data} total={analytics.fytd.total} />
        </div>
      </section>

      <TeamMonthlyActualBarCard data={analytics.monthly} total={analytics.fytd.total} fiscalYearLabel={fiscalYearLabel} />

      <AddTeamMemberPanel
        creating={creating}
        form={newMember}
        onChange={setNewMember}
        onSubmit={() => void createTeamMember()}
      />

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

function AddTeamMemberPanel({
  creating,
  form,
  onChange,
  onSubmit,
}: {
  creating: boolean;
  form: NewTeamMemberForm;
  onChange: (form: NewTeamMemberForm) => void;
  onSubmit: () => void;
}) {
  function update<K extends keyof NewTeamMemberForm>(key: K, value: NewTeamMemberForm[K]) {
    onChange({ ...form, [key]: value });
  }

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-3">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">Add Team Member</h2>
        <p className="mt-1 text-sm text-muted-foreground">Create a roster record before assigning the Team Member to Products or forecast lines.</p>
      </div>
      <form
        className="grid gap-3 md:grid-cols-2 xl:grid-cols-[0.8fr_1.2fr_1fr_1fr_0.8fr_0.9fr_1fr_0.7fr_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <TeamMemberField label="Staff ID">
          <Input
            aria-label="New team member staff ID"
            disabled={creating}
            placeholder="Optional"
            value={form.staffId}
            onChange={(event) => update("staffId", event.target.value)}
          />
        </TeamMemberField>
        <TeamMemberField label="Name">
          <Input
            aria-label="New team member name"
            disabled={creating}
            placeholder="Full name"
            value={form.name}
            onChange={(event) => update("name", event.target.value)}
          />
        </TeamMemberField>
        <TeamMemberField label="Role">
          <Input
            aria-label="New team member role"
            disabled={creating}
            placeholder="Role"
            value={form.role}
            onChange={(event) => update("role", event.target.value)}
          />
        </TeamMemberField>
        <TeamMemberField label="Team">
          <Input
            aria-label="New team member team"
            disabled={creating}
            placeholder="Team"
            value={form.team}
            onChange={(event) => update("team", event.target.value)}
          />
        </TeamMemberField>
        <TeamMemberField label="Bill Rate">
          <Input
            aria-label="New team member bill rate"
            className="numeric-cell"
            disabled={creating}
            inputMode="decimal"
            placeholder="0.00"
            value={form.billRate}
            onChange={(event) => update("billRate", event.target.value)}
          />
        </TeamMemberField>
        <TeamMemberField label="Employment">
          <select
            aria-label="New team member employment type"
            className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
            disabled={creating}
            value={form.employmentType}
            onChange={(event) => update("employmentType", event.target.value)}
          >
            <option value="Contractor">Contractor</option>
            <option value="FTE">FTE</option>
            <option value="Employee">Employee</option>
          </select>
        </TeamMemberField>
        <TeamMemberField label="Company">
          <Input
            aria-label="New team member contracting company"
            disabled={creating}
            placeholder="Company"
            value={form.contractingCompany}
            onChange={(event) => update("contractingCompany", event.target.value)}
          />
        </TeamMemberField>
        <TeamMemberField label="Status">
          <select
            aria-label="New team member status"
            className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
            disabled={creating}
            value={form.status}
            onChange={(event) => update("status", event.target.value)}
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </TeamMemberField>
        <div className="flex items-end">
          <Button className="w-full" disabled={creating} type="submit">
            <Plus className="h-4 w-4" />
            {creating ? "Adding" : "Add"}
          </Button>
        </div>
      </form>
    </section>
  );
}

function TeamMemberField({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="space-y-1">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function TeamActualPieCard({ title, data, total }: { title: string; data: TeamActualSlice[]; total: number }) {
  const hasData = data.some((row) => row.hours > 0);
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">{title}</h2>
          <div className="numeric-cell mt-1 text-2xl font-semibold text-primary">{formatHours(total)}</div>
        </div>
        <div className="text-right text-xs text-muted-foreground">{hasData ? `${data.length} logging` : "No logged hours"}</div>
      </div>
      <div className="relative mx-auto mt-1 aspect-square w-full max-w-96">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              cx="50%"
              cy="50%"
              data={hasData ? data : [{ teamMember: "No logged hours", hours: 1 }]}
              dataKey="hours"
              nameKey="teamMember"
              outerRadius="94%"
              paddingAngle={hasData ? 0.75 : 0}
            >
              {(hasData ? data : [{ teamMember: "No logged hours", hours: 1 }]).map((entry, index) => (
                <Cell key={entry.teamMember} fill={hasData ? PIE_COLORS[index % PIE_COLORS.length] : "hsl(var(--muted))"} />
              ))}
            </Pie>
            {hasData ? <Tooltip formatter={(value: number, name: string) => [`${formatHours(value)} hrs`, name]} /> : null}
          </PieChart>
        </ResponsiveContainer>
        {!hasData ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-center text-sm font-medium text-muted-foreground">
            No logged hours
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TeamMonthlyActualBarCard({ data, total, fiscalYearLabel }: { data: TeamActualMonth[]; total: number; fiscalYearLabel: string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Actual Hours by Fiscal Month</h2>
          <div className="numeric-cell mt-1 text-2xl font-semibold text-primary">{formatHours(total)}</div>
        </div>
        <div className="text-right text-xs text-muted-foreground">{fiscalYearLabel} FYTD</div>
      </div>
      <div className="mt-3 h-44">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis axisLine={false} dataKey="label" tickLine={false} />
            <YAxis axisLine={false} tickFormatter={(value: number) => formatHours(value)} tickLine={false} width={44} />
            <Tooltip formatter={(value: number) => [`${formatHours(value)} hrs`, "Actual"]} />
            <Bar dataKey="hours" fill="var(--spark-cyan)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
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

function blankTeamMemberForm(): NewTeamMemberForm {
  return {
    staffId: "",
    name: "",
    role: "",
    team: "",
    billRate: "",
    employmentType: "Contractor",
    contractingCompany: "",
    status: "active",
  };
}

function teamMemberPayload(form: NewTeamMemberForm): TeamMemberCreatePayload | string {
  const name = cleanText(form.name);
  const role = cleanText(form.role);
  const team = cleanText(form.team);
  const employmentType = cleanText(form.employmentType);
  const contractingCompany = cleanText(form.contractingCompany);
  const billRate = form.billRate.trim() === "" ? 0 : Number(form.billRate);
  const isContractor = employmentType.toLowerCase().includes("contract");

  if (!name || !role || !team || !employmentType) {
    return "Name, role, team, and employment type are required.";
  }
  if (!Number.isFinite(billRate) || billRate < 0) {
    return "Bill rate must be a valid non-negative number.";
  }
  if (isContractor && billRate <= 0) {
    return "Bill rate is required for contractors.";
  }
  if (isContractor && !contractingCompany) {
    return "Contracting company is required for contractors.";
  }

  return {
    staff_id: cleanText(form.staffId) || null,
    name,
    role,
    team,
    bill_rate: billRate,
    employment_type: employmentType,
    contracting_company: contractingCompany || null,
    status: form.status,
  };
}

function cleanText(value: string) {
  return value.trim();
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

type TeamActualSlice = {
  teamMember: string;
  hours: number;
};

type TeamActualPeriod = {
  label: string;
  data: TeamActualSlice[];
  total: number;
};

type TeamActualMonth = {
  label: string;
  hours: number;
};

function buildTeamActualAnalytics(rows: ReportedValueRow[], fiscalYear: number) {
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
    current: aggregateActualPeriod(
      rows.filter((row) => row.calendar_year === current.year && row.calendar_month === current.month),
      monthLabel(current.month),
    ),
    previous: aggregateActualPeriod(
      rows.filter((row) => row.calendar_year === previous.year && row.calendar_month === previous.month),
      monthLabel(previous.month),
    ),
    fytd: aggregateActualPeriod(fytdRows, "FYTD"),
    monthly: aggregateActualMonths(rows),
  };
}

function aggregateActualPeriod(rows: ReportedValueRow[], label: string): TeamActualPeriod {
  const hoursByMember = new Map<string, number>();
  for (const row of rows) {
    hoursByMember.set(row.team_member, (hoursByMember.get(row.team_member) ?? 0) + row.actual_hours);
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

function fiscalSequenceForCalendarMonth(calendarMonth: number) {
  return calendarMonth >= 7 ? calendarMonth - 6 : calendarMonth + 6;
}

const FISCAL_MONTH_LABELS = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"];

function monthLabel(calendarMonth: number) {
  return new Intl.DateTimeFormat(undefined, { month: "short" }).format(new Date(2026, calendarMonth - 1, 1));
}

function roundHours(value: number) {
  return Math.round(value * 10) / 10;
}
