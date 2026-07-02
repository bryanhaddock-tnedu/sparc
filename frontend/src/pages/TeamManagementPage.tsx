import { ArrowDown, ArrowUp, ChevronsUpDown, Plus, RotateCcw, Search, UserMinus } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type MouseEventHandler, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type Row,
  type SortingState,
} from "@tanstack/react-table";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { TeamMemberRankingsTable } from "../components/TeamMemberRankingsTable";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import { teamMemberDetailPath } from "../lib/routes";
import {
  buildTeamActualAnalytics,
  buildTeamMemberRankingRows,
  teamAnalyticsPath,
  teamDisplayName,
  type TeamActualMonth,
  type TeamActualSlice,
  type TeamRankingDimension,
} from "../lib/teamAnalytics";
import { formatBillRate } from "../lib/teamMembers";
import { formatHours } from "../lib/utils";
import type { ReportedValueRow, TeamMember, TeamMemberCreatePayload, TeamMemberStoryPointMetric } from "../types/api";

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

type TeamMemberRowGroup = {
  team: string;
  rows: Row<TeamMember>[];
  activeCount: number;
};

export function TeamManagementPage() {
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [reportedRows, setReportedRows] = useState<ReportedValueRow[]>([]);
  const [storyMetrics, setStoryMetrics] = useState<TeamMemberStoryPointMetric[]>([]);
  const [newMember, setNewMember] = useState<NewTeamMemberForm>(() => blankTeamMemberForm());
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [nameSearch, setNameSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [rankingDimension, setRankingDimension] = useState<TeamRankingDimension>("fytd_actual");
  const [sorting, setSorting] = useState<SortingState>([{ id: "name", desc: false }]);
  const [rosterStatusUpdatingId, setRosterStatusUpdatingId] = useState<number | null>(null);

  const loadTeamOverview = useCallback(async () => {
    const [memberRows, reportedValueRows, storyPointRows] = await Promise.all([
      api.teamMembers(),
      api.reportedValues({}, fiscalYear),
      api.teamMemberStoryPointMetrics(fiscalYear),
    ]);
    setMembers(memberRows);
    setReportedRows(reportedValueRows);
    setStoryMetrics(storyPointRows);
  }, [fiscalYear]);

  useEffect(() => {
    setLoading(true);
    loadTeamOverview()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load team"))
      .finally(() => setLoading(false));
  }, [loadTeamOverview]);

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

  const updateRosterStatus = useCallback(
    async (member: TeamMember, nextStatus: "active" | "inactive") => {
      if (nextStatus === "inactive" && !window.confirm(`Remove ${member.name} from the active roster? Historical SPARC data will stay intact.`)) {
        return;
      }

      setRosterStatusUpdatingId(member.id);
      setActionError(null);
      setNotice(null);
      try {
        const updated = await api.updateTeamMember(member.slug || member.id, { status: nextStatus });
        await loadTeamOverview();
        setNotice(
          nextStatus === "active"
            ? `${updated.name} was restored to the active roster.`
            : `${updated.name} was removed from the active roster.`,
        );
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Unable to update roster status");
      } finally {
        setRosterStatusUpdatingId(null);
      }
    },
    [loadTeamOverview],
  );

  const analytics = useMemo(() => buildTeamActualAnalytics(reportedRows, members, fiscalYear), [reportedRows, members, fiscalYear]);
  const rankingRows = useMemo(
    () => buildTeamMemberRankingRows(reportedRows, members, fiscalYear, storyMetrics),
    [fiscalYear, members, reportedRows, storyMetrics],
  );
  const normalizedNameSearch = nameSearch.trim().toLowerCase();
  const activeMemberCount = members.filter((member) => member.status === "active").length;
  const inactiveMemberCount = members.length - activeMemberCount;
  const filteredMembers = useMemo(() => {
    const rosterMembers = includeInactive ? members : members.filter((member) => member.status === "active");
    if (!normalizedNameSearch) return rosterMembers;
    return rosterMembers.filter((member) => member.name.toLowerCase().split(/\s+/).some((namePart) => namePart.startsWith(normalizedNameSearch)));
  }, [includeInactive, members, normalizedNameSearch]);

  const columns = useMemo<ColumnDef<TeamMember>[]>(
    () => [
      {
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => (
          <Link className="font-medium text-primary hover:underline" to={teamMemberDetailPath(row.original)}>
            {row.original.name}
          </Link>
        ),
      },
      { accessorKey: "role", header: "Role" },
      {
        accessorKey: "bill_rate",
        header: "Bill Rate",
        cell: ({ row }) => (
          <span className="numeric-cell whitespace-nowrap font-medium text-primary" title="Edit bill rate on the Team Member profile">
            {formatBillRate(row.original.bill_rate, row.original.employment_type, { includeUnit: true })}
          </span>
        ),
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
      {
        id: "roster_action",
        header: "Roster",
        enableSorting: false,
        cell: ({ row }) => {
          const member = row.original;
          const isActive = member.status === "active";
          const busy = rosterStatusUpdatingId === member.id;
          return (
            <div className="flex justify-end">
              <Button
                aria-label={isActive ? `Remove ${member.name} from active roster` : `Restore ${member.name} to active roster`}
                disabled={busy}
                onClick={() => void updateRosterStatus(member, isActive ? "inactive" : "active")}
                size="sm"
                variant="outline"
              >
                {isActive ? <UserMinus className="h-4 w-4" /> : <RotateCcw className="h-4 w-4" />}
                {busy ? "Saving" : isActive ? "Remove" : "Restore"}
              </Button>
            </div>
          );
        },
      },
    ],
    [rosterStatusUpdatingId, updateRosterStatus],
  );

  const table = useReactTable({
    data: filteredMembers,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  const groupedMemberRows = groupTeamMemberRows(table.getRowModel().rows);

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;

  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold">Team Management</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {activeMemberCount} active Team Members / {inactiveMemberCount} inactive / {fiscalYearLabel} ({fiscalYearRangeLabel})
          </p>
        </div>
        <PageNav current="team" />
      </div>

      {notice ? <div className="rounded-md border border-[color:var(--spark-cyan)] bg-accent/10 px-3 py-2 text-sm text-primary">{notice}</div> : null}
      {actionError ? <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{actionError}</div> : null}

      <section className="overflow-x-auto pb-1">
        <div className="grid min-w-[1080px] grid-cols-3 gap-4">
          <TeamActualPieCard title={`Previous Month by Team (${analytics.previous.label})`} data={analytics.previous.data} total={analytics.previous.total} />
          <TeamActualPieCard title={`Current Month by Team (${analytics.current.label})`} data={analytics.current.data} total={analytics.current.total} />
          <TeamActualPieCard title={`${fiscalYearLabel} FYTD by Team`} data={analytics.fytd.data} total={analytics.fytd.total} />
        </div>
      </section>

      <TeamMonthlyActualBarCard data={analytics.monthly} total={analytics.fytd.total} fiscalYearLabel={fiscalYearLabel} />

      <TeamMemberRankingsTable
        description="All rostered Team Members ranked by the selected hours, ticket, or story point signal."
        dimension={rankingDimension}
        onDimensionChange={setRankingDimension}
        rows={rankingRows}
        title="All Team Member Rankings"
      />

      <AddTeamMemberPanel
        creating={creating}
        form={newMember}
        onChange={setNewMember}
        onSubmit={() => void createTeamMember()}
      />

      <section className="flex flex-col justify-between gap-3 rounded-lg border bg-card p-4 md:flex-row md:items-center">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Roster</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Showing {filteredMembers.length} of {includeInactive ? members.length : activeMemberCount} Team Members across {teamGroupCountLabel(groupedMemberRows.length)}.
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 md:w-auto md:flex-row md:items-center">
          <Button
            disabled={inactiveMemberCount === 0}
            onClick={() => setIncludeInactive((current) => !current)}
            type="button"
            variant={includeInactive ? "secondary" : "outline"}
          >
            {includeInactive ? "Hide inactive" : `Show inactive (${inactiveMemberCount})`}
          </Button>
          <label className="relative block w-full md:w-80">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              aria-label="Search team members by name"
              className="pl-9"
              placeholder="Search name prefix"
              value={nameSearch}
              onChange={(event) => setNameSearch(event.target.value)}
            />
          </label>
        </div>
      </section>

      {groupedMemberRows.length ? (
        <div className="space-y-3">
          {groupedMemberRows.map((group) => (
            <section key={group.team} className="overflow-hidden rounded-lg border bg-card">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-secondary/50 px-3 py-2">
                <div className="min-w-0">
                  <Link className="truncate text-base font-semibold text-primary hover:underline" to={teamAnalyticsPath(group.team)}>
                    {group.team}
                  </Link>
                  <p className="text-xs text-muted-foreground">{teamMemberCountLabel(group.rows.length)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge className="border-primary/40 text-primary">{group.activeCount} active</Badge>
                  {group.rows.length - group.activeCount > 0 ? (
                    <Badge className="border-muted text-muted-foreground">{group.rows.length - group.activeCount} inactive</Badge>
                  ) : null}
                </div>
              </div>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    {table.getHeaderGroups().map((headerGroup) => (
                      <TableRow key={headerGroup.id}>
                        {headerGroup.headers.map((header) => (
                          <TableHead key={header.id}>
                            {header.isPlaceholder ? null : (
                              <HeaderSortButton
                                canSort={header.column.getCanSort()}
                                direction={header.column.getIsSorted()}
                                onClick={(event) => header.column.getToggleSortingHandler()?.(event)}
                              >
                                {flexRender(header.column.columnDef.header, header.getContext())}
                              </HeaderSortButton>
                            )}
                          </TableHead>
                        ))}
                      </TableRow>
                    ))}
                  </TableHeader>
                  <TableBody>
                    {group.rows.map((row) => (
                      <TableRow key={row.id}>
                        {row.getVisibleCells().map((cell) => (
                          <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border bg-card p-5 text-sm text-muted-foreground">
          No {includeInactive ? "" : "active "}Team Members match that name prefix.
        </div>
      )}
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

function groupTeamMemberRows(rows: Row<TeamMember>[]): TeamMemberRowGroup[] {
  const groups = new Map<string, Row<TeamMember>[]>();
  rows.forEach((row) => {
    const team = teamDisplayName(row.original.team);
    groups.set(team, [...(groups.get(team) ?? []), row]);
  });

  return [...groups.entries()]
    .map(([team, groupRows]) => ({
      team,
      rows: groupRows,
      activeCount: groupRows.filter((row) => row.original.status === "active").length,
    }))
    .sort((left, right) => compareTeamNames(left.team, right.team));
}

function compareTeamNames(left: string, right: string) {
  if (left === "Unassigned" && right !== "Unassigned") {
    return 1;
  }
  if (right === "Unassigned" && left !== "Unassigned") {
    return -1;
  }
  return left.localeCompare(right, undefined, { sensitivity: "base" });
}

function teamMemberCountLabel(count: number) {
  return `${count} Team ${count === 1 ? "Member" : "Members"}`;
}

function teamGroupCountLabel(count: number) {
  return `${count} ${count === 1 ? "team" : "teams"}`;
}

function HeaderSortButton({
  canSort,
  children,
  direction,
  onClick,
}: {
  canSort: boolean;
  children: ReactNode;
  direction: false | "asc" | "desc";
  onClick: MouseEventHandler<HTMLButtonElement>;
}) {
  if (!canSort) {
    return <span className="text-xs font-semibold uppercase text-muted-foreground">{children}</span>;
  }

  const Icon = direction === "asc" ? ArrowUp : direction === "desc" ? ArrowDown : ChevronsUpDown;
  const label = direction === "asc" ? "ascending" : direction === "desc" ? "descending" : "sortable";

  return (
    <button
      aria-label={`Sort by ${String(children)} (${label})`}
      className="flex w-full items-center gap-1 text-left text-xs font-semibold uppercase text-muted-foreground hover:text-primary"
      onClick={onClick}
      type="button"
    >
      <span className="min-w-0 truncate">{children}</span>
      <Icon className="h-3.5 w-3.5 shrink-0" />
    </button>
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
        <div className="text-right text-xs text-muted-foreground">{hasData ? `${data.length} teams logging` : "No logged hours"}</div>
      </div>
      <div className="relative mx-auto mt-1 aspect-square w-full max-w-96">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              cx="50%"
              cy="50%"
              data={hasData ? data : [{ team: "No logged hours", hours: 1 }]}
              dataKey="hours"
              nameKey="team"
              outerRadius="94%"
              paddingAngle={hasData ? 0.75 : 0}
            >
              {(hasData ? data : [{ team: "No logged hours", hours: 1 }]).map((entry, index) => (
                <Cell key={entry.team} fill={hasData ? PIE_COLORS[index % PIE_COLORS.length] : "hsl(var(--muted))"} />
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
