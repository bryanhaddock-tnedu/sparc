import { Pencil, Save, X } from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { MetricCard } from "../components/MetricCard";
import { PageNav } from "../components/PageNav";
import { ReportedValuesTable } from "../components/ReportedValuesTable";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import { formatBillRate } from "../lib/teamMembers";
import { formatCurrency, formatHours } from "../lib/utils";
import type { FiscalMonth, ReportedValueRow, TeamMember, TeamMemberActualWorklog, TeamMemberProducts } from "../types/api";

const CHART_COLORS = ["var(--spark-cyan)", "var(--spark-orange)", "var(--spark-navy)", "var(--spark-red)", "#8fb3d9", "#d6d94f", "#7a86a8"];

type ProfileFormState = {
  name: string;
  role: string;
  team: string;
  billRate: string;
  employmentType: string;
  contractingCompany: string;
  status: string;
};

export function TeamMemberDetailPage() {
  const params = useParams();
  const teamMemberId = Number(params.teamMemberId);
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [data, setData] = useState<TeamMemberProducts | null>(null);
  const [reportedRows, setReportedRows] = useState<ReportedValueRow[]>([]);
  const [actualWorklogs, setActualWorklogs] = useState<TeamMemberActualWorklog[]>([]);
  const [worklogMonthId, setWorklogMonthId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [forecastDrafts, setForecastDrafts] = useState<Record<string, string>>({});
  const [savingForecastCells, setSavingForecastCells] = useState<Record<string, boolean>>({});
  const [form, setForm] = useState<ProfileFormState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  async function loadData() {
    const [productsResult, reportedRowsResult, actualWorklogsResult] = await Promise.all([
      api.teamMemberProducts(teamMemberId, fiscalYear),
      api.reportedValues({ team_member_id: teamMemberId }, fiscalYear),
      api.teamMemberActualWorklogs(teamMemberId, fiscalYear),
    ]);
    setData(productsResult);
    setReportedRows(reportedRowsResult);
    setActualWorklogs(actualWorklogsResult);
    setForecastDrafts({});
    setWorklogMonthId((current) => {
      if (!current) {
        return defaultWorklogMonthId(actualWorklogsResult);
      }
      if (current === "all" || actualWorklogsResult.some((row) => String(row.fiscal_month_id) === current)) {
        return current;
      }
      return defaultWorklogMonthId(actualWorklogsResult);
    });
  }

  useEffect(() => {
    setLoading(true);
    setWorklogMonthId("");
    loadData()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load team member"))
      .finally(() => setLoading(false));
  }, [teamMemberId, fiscalYear]);

  const monthOptions = useMemo(() => worklogMonthOptions(actualWorklogs), [actualWorklogs]);
  const selectedWorklogs = useMemo(
    () => {
      const selectedMonthId = worklogMonthId || "all";
      return selectedMonthId === "all" ? actualWorklogs : actualWorklogs.filter((row) => String(row.fiscal_month_id) === selectedMonthId);
    },
    [actualWorklogs, worklogMonthId],
  );
  const worklogSummary = useMemo(() => summarizeWorklogs(selectedWorklogs), [selectedWorklogs]);
  const memberAnalytics = useMemo(() => buildMemberAnalytics(reportedRows, data?.months ?? []), [reportedRows, data?.months]);
  const forecastLines = useMemo(
    () => buildMemberForecastLines(data?.products ?? [], reportedRows, data?.months ?? [], data?.team_member.bill_rate ?? 0),
    [data?.products, reportedRows, data?.months, data?.team_member.bill_rate],
  );

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!data) return null;

  const member = data.team_member;
  const forecastHours = data.products.reduce((total, row) => total + row.forecast_hours, 0);
  const actualHours = data.products.reduce((total, row) => total + row.actual_hours, 0);
  const forecastCost = data.products.reduce((total, row) => total + row.forecast_cost, 0);
  const actualCost = data.products.reduce((total, row) => total + row.actual_cost, 0);

  function updateForecastDraft(line: MemberForecastLine, cell: MemberForecastMonthCell, value: string) {
    const key = memberForecastDraftKey(line, cell);
    setForecastDrafts((current) => {
      const next = { ...current };
      if (value === String(cell.forecast_hours)) {
        delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
  }

  async function saveForecastCell(line: MemberForecastLine, cell: MemberForecastMonthCell) {
    const key = memberForecastDraftKey(line, cell);
    const draft = forecastDrafts[key];
    if (draft === undefined) return;

    const value = draft.trim() === "" ? 0 : Number(draft);
    if (!Number.isFinite(value) || value < 0) return;

    if (value === cell.forecast_hours) {
      setForecastDrafts((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      return;
    }

    setSavingForecastCells((current) => ({ ...current, [key]: true }));
    setError(null);
    try {
      await api.upsertForecast({
        product_id: line.product_id,
        team_member_id: member.id,
        bucket_id: line.bucket_id,
        fiscal_month_id: cell.fiscal_month_id,
        hours: value,
      });
      setForecastDrafts((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save forecast");
    } finally {
      setSavingForecastCells((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
    }
  }

  function startEditing() {
    setForm(formFromMember(member));
    setFormError(null);
    setEditing(true);
  }

  function cancelEditing() {
    setEditing(false);
    setForm(null);
    setFormError(null);
  }

  async function saveProfile() {
    if (!form) return;
    const nextBillRate = form.billRate.trim() === "" ? 0 : Number(form.billRate);
    if (!form.name.trim() || !form.role.trim() || !form.team.trim() || !form.employmentType.trim()) {
      setFormError("Name, role, team, and employment type are required.");
      return;
    }
    if (!Number.isFinite(nextBillRate) || nextBillRate < 0) {
      setFormError("Bill rate must be a valid non-negative number.");
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      await api.updateTeamMember(member.id, {
        name: form.name.trim(),
        role: form.role.trim(),
        team: form.team.trim(),
        bill_rate: nextBillRate,
        employment_type: form.employmentType.trim(),
        contracting_company: form.contractingCompany.trim() || null,
        status: form.status,
      });
      await loadData();
      setEditing(false);
      setForm(null);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Unable to save team member");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <section className="flex flex-col justify-between gap-4 border-b pb-5 lg:flex-row lg:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold">{member.name}</h1>
            <Badge className={member.status === "active" ? "border-primary/40 text-primary" : "border-muted text-muted-foreground"}>
              {member.status}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {member.role} / {member.team} / {fiscalYearLabel} ({fiscalYearRangeLabel})
          </p>
        </div>
        <PageNav />
      </section>

      <section className="grid gap-4 xl:grid-cols-[340px_1fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle>Profile</CardTitle>
              {editing ? (
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={cancelEditing} disabled={saving}>
                    <X className="h-4 w-4" />
                    Cancel
                  </Button>
                  <Button size="sm" onClick={() => void saveProfile()} disabled={saving}>
                    <Save className="h-4 w-4" />
                    {saving ? "Saving" : "Save"}
                  </Button>
                </div>
              ) : (
                <Button size="sm" variant="outline" onClick={startEditing}>
                  <Pencil className="h-4 w-4" />
                  Edit
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {editing && form ? (
              <>
                <ProfileField label="Name" value={form.name} onChange={(name) => setForm({ ...form, name })} disabled={saving} />
                <ProfileField label="Role" value={form.role} onChange={(role) => setForm({ ...form, role })} disabled={saving} />
                <ProfileField label="Team" value={form.team} onChange={(team) => setForm({ ...form, team })} disabled={saving} />
                <ProfileField
                  label="Employment Type"
                  value={form.employmentType}
                  onChange={(employmentType) => setForm({ ...form, employmentType })}
                  disabled={saving}
                />
                <ProfileField
                  label="Bill Rate"
                  value={form.billRate}
                  onChange={(billRate) => setForm({ ...form, billRate })}
                  disabled={saving}
                  inputMode="decimal"
                  placeholder="Not set"
                />
                <ProfileField
                  label="Contracting Company"
                  value={form.contractingCompany}
                  onChange={(contractingCompany) => setForm({ ...form, contractingCompany })}
                  disabled={saving}
                />
                <ProfileSelect
                  label="Status"
                  value={form.status}
                  onChange={(status) => setForm({ ...form, status })}
                  disabled={saving}
                  options={["active", "inactive"]}
                />
                {formError ? <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-destructive">{formError}</div> : null}
              </>
            ) : (
              <>
                <ProfileRow label="Role" value={member.role} />
                <ProfileRow label="Team" value={member.team} />
                <ProfileRow label="Bill Rate" value={formatBillRate(member.bill_rate, member.employment_type, { includeUnit: true })} />
                <ProfileRow label="Employment Type" value={member.employment_type} />
                <ProfileRow label="Contracting Company" value={member.contracting_company ?? ""} />
                <ProfileRow label="Created" value={formatDate(member.created_at)} />
                <ProfileRow label="Last Updated" value={formatDate(member.updated_at)} />
              </>
            )}
          </CardContent>
        </Card>
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Forecast Hours FY" value={formatHours(forecastHours)} />
            <MetricCard label="Actual Hours FYTD" value={formatHours(actualHours)} />
            <MetricCard label="Forecast Cost FY" value={formatCurrency(forecastCost)} />
            <MetricCard label="Actual Cost FYTD" value={formatCurrency(actualCost)} />
          </div>
          <div className="grid gap-3 xl:grid-cols-[1.35fr_0.65fr]">
            <MemberMonthlyActualBarCard data={memberAnalytics.monthlyActuals} total={actualHours} />
            <MemberProductMixCard data={memberAnalytics.actualByProduct} />
          </div>
        </div>
      </section>

      <MemberForecastTable
        drafts={forecastDrafts}
        lines={forecastLines}
        onDraftChange={updateForecastDraft}
        onDraftCommit={saveForecastCell}
        savingCells={savingForecastCells}
      />

      <ReportedValuesTable rows={reportedRows} showProduct />

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Actual Worklog Audit</h2>
            <p className="mt-1 text-sm text-muted-foreground">Jira worklogs imported into SPARC for {member.name}.</p>
          </div>
          <label className="text-sm">
            <span className="sr-only">Actual worklog month</span>
            <select
              className="h-9 min-w-44 rounded-md border border-input bg-background px-3 py-1 text-sm"
              value={worklogMonthId || "all"}
              onChange={(event) => setWorklogMonthId(event.target.value)}
            >
              <option value="all">All FY</option>
              {monthOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="grid gap-3 sm:grid-cols-4">
          <MetricCard label="Selected Hours" value={formatHours(worklogSummary.hours)} />
          <MetricCard label="Worklogs" value={`${worklogSummary.worklogCount}`} />
          <MetricCard label="Tickets" value={`${worklogSummary.ticketCount}`} />
          <MetricCard label="Largest Entry" value={formatHours(worklogSummary.largestEntry)} />
        </div>
        <div className="overflow-hidden rounded-lg border bg-card">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Ticket</TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead>Bucket</TableHead>
                  <TableHead>Jira Project</TableHead>
                  <TableHead>Sync</TableHead>
                  <TableHead className="text-right">Hours</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {selectedWorklogs.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.worked_on ? formatDateOnly(row.worked_on) : "-"}</TableCell>
                    <TableCell className="font-medium text-primary">{row.source_ticket_key ?? row.source_issue_id ?? "-"}</TableCell>
                    <TableCell>
                      <Link className="font-medium text-primary hover:underline" to={`/products/${row.product_id}`}>
                        {row.product}
                      </Link>
                    </TableCell>
                    <TableCell>{row.bucket}</TableCell>
                    <TableCell>{row.source_project_key ?? "-"}</TableCell>
                    <TableCell>{row.sync_completed_at ? formatDateTime(row.sync_completed_at) : "-"}</TableCell>
                    <TableCell className="numeric-cell text-right font-semibold">{formatHours(row.hours)}</TableCell>
                  </TableRow>
                ))}
                {selectedWorklogs.length === 0 ? (
                  <TableRow>
                    <TableCell className="py-6 text-center text-sm text-muted-foreground" colSpan={7}>
                      No actual Jira worklogs were imported for this selection.
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Product Associations</h2>
        <div className="overflow-hidden rounded-lg border bg-card">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Bucket</TableHead>
                  <TableHead>Forecast Hours</TableHead>
                  <TableHead>Actual Hours</TableHead>
                  <TableHead>Forecast Cost</TableHead>
                  <TableHead>Actual Cost</TableHead>
                  <TableHead>Remaining Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.products.map((row) => (
                  <TableRow key={`${row.product_id}-${row.bucket_id}`}>
                    <TableCell>
                      <Link className="font-medium text-primary hover:underline" to={`/products/${row.product_id}`}>
                        {row.product}
                      </Link>
                    </TableCell>
                    <TableCell>{row.bucket}</TableCell>
                    <TableCell className="numeric-cell">{formatHours(row.forecast_hours)}</TableCell>
                    <TableCell className="numeric-cell">{formatHours(row.actual_hours)}</TableCell>
                    <TableCell className="numeric-cell">{formatCurrency(row.forecast_cost)}</TableCell>
                    <TableCell className="numeric-cell">{formatCurrency(row.actual_cost)}</TableCell>
                    <TableCell className="numeric-cell">{formatCurrency(row.remaining_cost)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </section>
    </div>
  );
}

function ProfileRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b pb-2 last:border-0 last:pb-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value || "-"}</span>
    </div>
  );
}

function ProfileField({
  label,
  value,
  onChange,
  disabled,
  inputMode,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  inputMode?: "decimal";
  placeholder?: string;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-muted-foreground">{label}</span>
      <Input
        disabled={disabled}
        inputMode={inputMode}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function ProfileSelect({
  label,
  value,
  onChange,
  disabled,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  options: string[];
}) {
  return (
    <label className="block space-y-1">
      <span className="text-muted-foreground">{label}</span>
      <select
        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        disabled={disabled}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function MemberMonthlyActualBarCard({ data, total }: { data: MemberMonthlyHours[]; total: number }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Actual Hours by Fiscal Month</h2>
          <div className="numeric-cell mt-1 text-2xl font-semibold text-primary">{formatHours(total)}</div>
        </div>
        <div className="text-right text-xs text-muted-foreground">FYTD actuals</div>
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

function MemberProductMixCard({ data }: { data: MemberProductHours[] }) {
  const hasData = data.some((row) => row.hours > 0);
  const chartData = hasData ? data : [{ product: "No actuals", hours: 1 }];
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Actual Mix by Product</h2>
          <div className="numeric-cell mt-1 text-2xl font-semibold text-primary">{formatHours(data.reduce((sum, row) => sum + row.hours, 0))}</div>
        </div>
        <div className="text-right text-xs text-muted-foreground">{hasData ? `${data.length} products` : "No actuals"}</div>
      </div>
      <div className="relative mt-2 h-44">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={chartData} dataKey="hours" nameKey="product" outerRadius="88%" paddingAngle={hasData ? 1 : 0}>
              {chartData.map((entry, index) => (
                <Cell key={entry.product} fill={hasData ? CHART_COLORS[index % CHART_COLORS.length] : "hsl(var(--muted))"} />
              ))}
            </Pie>
            {hasData ? <Tooltip formatter={(value: number, name: string) => [`${formatHours(value)} hrs`, name]} /> : null}
          </PieChart>
        </ResponsiveContainer>
        {!hasData ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-center text-sm font-medium text-muted-foreground">
            No actuals yet
          </div>
        ) : null}
      </div>
    </div>
  );
}

function MemberForecastTable({
  drafts,
  lines,
  onDraftChange,
  onDraftCommit,
  savingCells,
}: {
  drafts: Record<string, string>;
  lines: MemberForecastLine[];
  onDraftChange: (line: MemberForecastLine, cell: MemberForecastMonthCell, value: string) => void;
  onDraftCommit: (line: MemberForecastLine, cell: MemberForecastMonthCell) => void;
  savingCells: Record<string, boolean>;
}) {
  const monthlyTotals =
    lines[0]?.months.map((month, index) => {
      return lines.reduce(
        (acc, line) => {
          const cell = line.months[index];
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
      <div>
        <h2 className="text-lg font-semibold">Forecast by Product and Bucket</h2>
        <p className="mt-1 text-sm text-muted-foreground">Manage this team member&apos;s forecasted hours across each fiscal month.</p>
      </div>
      {lines.length ? (
        <div className="overflow-hidden rounded-lg border bg-card">
          <div className="overflow-x-auto">
            <table className="w-full table-fixed border-collapse text-xs">
              <colgroup>
                <col className="w-44" />
                <col className="w-20" />
                {lines[0].months.map((month) => (
                  <col key={month.fiscal_month_id} className="w-16" />
                ))}
                <col className="w-24" />
              </colgroup>
              <thead>
                <tr className="border-b bg-secondary/60">
                  <th className="sticky left-0 z-10 bg-secondary px-2 py-2 text-left text-[11px] font-semibold uppercase text-muted-foreground">
                    Product / Bucket
                  </th>
                  <th className="sticky left-44 z-10 bg-secondary px-2 py-2 text-left text-[11px] font-semibold uppercase text-muted-foreground">
                    Metric
                  </th>
                  {lines[0].months.map((month) => (
                    <th key={month.fiscal_month_id} className="px-1 py-2 text-right text-[11px] font-semibold uppercase text-muted-foreground">
                      {month.label}
                    </th>
                  ))}
                  <th className="px-1 py-2 text-right text-[11px] font-semibold uppercase text-muted-foreground">FY Total</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => (
                  <Fragment key={`${line.product_id}-${line.bucket_id}`}>
                    <tr className="border-t align-middle">
                      <td rowSpan={4} className="sticky left-0 z-10 bg-card px-2 py-2 align-top">
                        <Link className="block truncate font-medium text-primary hover:underline" to={`/products/${line.product_id}`}>
                          {line.product}
                        </Link>
                        <div className="mt-1 truncate text-[11px] text-muted-foreground">{line.bucket}</div>
                      </td>
                      <TeamMemberMetricLabel label="Forecast" />
                      {line.months.map((cell) => (
                        <td key={cell.fiscal_month_id} className="px-1 py-1">
                          <MemberForecastInput
                            cell={cell}
                            dirty={drafts[memberForecastDraftKey(line, cell)] !== undefined}
                            line={line}
                            onChange={(value) => onDraftChange(line, cell, value)}
                            onCommit={() => onDraftCommit(line, cell)}
                            saving={savingCells[memberForecastDraftKey(line, cell)] === true}
                            value={drafts[memberForecastDraftKey(line, cell)] ?? String(cell.forecast_hours)}
                          />
                        </td>
                      ))}
                      <TeamMemberValueCell value={formatHours(line.totals.forecast_hours)} strong />
                    </tr>
                    <tr>
                      <TeamMemberMetricLabel label="Actual" muted />
                      {line.months.map((cell) => (
                        <TeamMemberValueCell key={cell.fiscal_month_id} value={formatHours(cell.actual_hours)} muted />
                      ))}
                      <TeamMemberValueCell value={formatHours(line.totals.actual_hours)} muted strong />
                    </tr>
                    <tr>
                      <TeamMemberMetricLabel label="Fcst $" />
                      {line.months.map((cell) => (
                        <TeamMemberValueCell key={cell.fiscal_month_id} value={formatCurrency(cell.forecast_cost)} />
                      ))}
                      <TeamMemberValueCell value={formatCurrency(line.totals.forecast_cost)} strong />
                    </tr>
                    <tr className="border-b">
                      <TeamMemberMetricLabel label="Var $" />
                      {line.months.map((cell) => (
                        <TeamMemberValueCell
                          key={cell.fiscal_month_id}
                          className={cell.variance_cost > 0 ? "text-destructive" : "text-primary"}
                          value={formatCurrency(cell.variance_cost)}
                        />
                      ))}
                      <TeamMemberValueCell
                        className={line.totals.variance_cost > 0 ? "text-destructive" : "text-primary"}
                        strong
                        value={formatCurrency(line.totals.variance_cost)}
                      />
                    </tr>
                  </Fragment>
                ))}
                <tr className="border-t bg-secondary/50 font-semibold">
                  <td rowSpan={4} className="sticky left-0 z-10 bg-secondary px-2 py-2 align-top">
                    Member Total
                  </td>
                  <TeamMemberMetricLabel label="Forecast" total />
                  {monthlyTotals.map((totals) => (
                    <TeamMemberValueCell key={totals.fiscalMonthId} value={formatHours(totals.forecast)} total strong />
                  ))}
                  <TeamMemberValueCell value={formatHours(lines.reduce((sum, line) => sum + line.totals.forecast_hours, 0))} total strong />
                </tr>
                <tr className="bg-secondary/50 font-semibold">
                  <TeamMemberMetricLabel label="Actual" muted total />
                  {monthlyTotals.map((totals) => (
                    <TeamMemberValueCell key={totals.fiscalMonthId} value={formatHours(totals.actual)} muted total strong />
                  ))}
                  <TeamMemberValueCell value={formatHours(lines.reduce((sum, line) => sum + line.totals.actual_hours, 0))} muted total strong />
                </tr>
                <tr className="bg-secondary/50 font-semibold">
                  <TeamMemberMetricLabel label="Fcst $" total />
                  {monthlyTotals.map((totals) => (
                    <TeamMemberValueCell key={totals.fiscalMonthId} value={formatCurrency(totals.cost)} total strong />
                  ))}
                  <TeamMemberValueCell value={formatCurrency(lines.reduce((sum, line) => sum + line.totals.forecast_cost, 0))} total strong />
                </tr>
                <tr className="bg-secondary/50 font-semibold">
                  <TeamMemberMetricLabel label="Var $" total />
                  {monthlyTotals.map((totals) => (
                    <TeamMemberValueCell
                      key={totals.fiscalMonthId}
                      className={totals.variance > 0 ? "text-destructive" : "text-primary"}
                      value={formatCurrency(totals.variance)}
                      total
                      strong
                    />
                  ))}
                  <TeamMemberValueCell
                    className={lines.reduce((sum, line) => sum + line.totals.variance_cost, 0) > 0 ? "text-destructive" : "text-primary"}
                    value={formatCurrency(lines.reduce((sum, line) => sum + line.totals.variance_cost, 0))}
                    total
                    strong
                  />
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">
          No forecast or actual lines exist for this team member in the selected fiscal year yet.
        </div>
      )}
    </section>
  );
}

function MemberForecastInput({
  cell,
  dirty,
  line,
  onChange,
  onCommit,
  saving,
  value,
}: {
  cell: MemberForecastMonthCell;
  dirty: boolean;
  line: MemberForecastLine;
  onChange: (value: string) => void;
  onCommit: () => void;
  saving: boolean;
  value: string;
}) {
  const numericValue = Number(value);
  const invalid = value !== "" && (!Number.isFinite(numericValue) || numericValue < 0);
  return (
    <Input
      aria-label={`${line.product} ${line.bucket} ${cell.label} forecast hours`}
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

function TeamMemberMetricLabel({ label, muted, total }: { label: string; muted?: boolean; total?: boolean }) {
  return (
    <td
      className={`sticky left-44 z-10 px-2 py-1.5 text-[11px] font-semibold uppercase ${
        total ? "bg-secondary" : "bg-card"
      } ${muted ? "text-muted-foreground" : "text-foreground"}`}
    >
      {label}
    </td>
  );
}

function TeamMemberValueCell({
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

function formFromMember(member: TeamMember): ProfileFormState {
  return {
    name: member.name,
    role: member.role,
    team: member.team,
    billRate: member.bill_rate > 0 ? String(member.bill_rate) : "",
    employmentType: member.employment_type,
    contractingCompany: member.contracting_company ?? "",
    status: member.status,
  };
}

function worklogMonthOptions(rows: TeamMemberActualWorklog[]) {
  const options = new Map<string, string>();
  for (const row of rows) {
    options.set(String(row.fiscal_month_id), row.month_label);
  }
  return Array.from(options, ([id, label]) => ({ id, label }));
}

function summarizeWorklogs(rows: TeamMemberActualWorklog[]) {
  const ticketKeys = new Set(rows.map((row) => row.source_ticket_key ?? row.source_issue_id ?? `entry-${row.id}`));
  const hours = rows.reduce((total, row) => total + row.hours, 0);
  const largestEntry = rows.reduce((largest, row) => Math.max(largest, row.hours), 0);
  return {
    hours,
    largestEntry,
    ticketCount: ticketKeys.size,
    worklogCount: rows.length,
  };
}

function defaultWorklogMonthId(rows: TeamMemberActualWorklog[]) {
  const previousMonthKey = previousCalendarMonthKey();
  const previousMonthRow = rows.find((row) => rowCalendarMonthKey(row) === previousMonthKey);
  if (previousMonthRow) return String(previousMonthRow.fiscal_month_id);

  const latestRow = rows.reduce<TeamMemberActualWorklog | null>((latest, row) => {
    if (!row.worked_on) return latest;
    if (!latest?.worked_on) return row;
    return row.worked_on > latest.worked_on ? row : latest;
  }, null);
  return latestRow ? String(latestRow.fiscal_month_id) : "all";
}

function previousCalendarMonthKey() {
  const now = new Date();
  const previous = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return `${previous.getFullYear()}-${previous.getMonth() + 1}`;
}

function rowCalendarMonthKey(row: TeamMemberActualWorklog) {
  if (!row.worked_on) return "";
  const [year, month] = row.worked_on.split("-");
  return `${year}-${Number(month)}`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function formatDateOnly(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(year, month - 1, day));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

type MemberMonthlyHours = {
  label: string;
  hours: number;
};

type MemberProductHours = {
  product: string;
  hours: number;
};

type MemberForecastMonthCell = {
  fiscal_month_id: number;
  label: string;
  forecast_hours: number;
  actual_hours: number;
  forecast_cost: number;
  actual_cost: number;
  variance_cost: number;
};

type MemberForecastTotals = {
  forecast_hours: number;
  actual_hours: number;
  forecast_cost: number;
  actual_cost: number;
  variance_cost: number;
};

type MemberForecastLine = {
  product_id: number;
  product: string;
  bucket_id: number;
  bucket: string;
  months: MemberForecastMonthCell[];
  totals: MemberForecastTotals;
};

function buildMemberAnalytics(rows: ReportedValueRow[], months: FiscalMonth[]) {
  const monthlyActuals = months.map((month) => ({
    label: month.label,
    hours: roundHours(rows.filter((row) => row.fiscal_month_id === month.id).reduce((sum, row) => sum + row.actual_hours, 0)),
  }));

  const hoursByProduct = new Map<string, number>();
  for (const row of rows) {
    hoursByProduct.set(row.product, (hoursByProduct.get(row.product) ?? 0) + row.actual_hours);
  }

  const actualByProduct = Array.from(hoursByProduct, ([product, hours]) => ({ product, hours: roundHours(hours) }))
    .filter((row) => row.hours > 0)
    .sort((left, right) => right.hours - left.hours || left.product.localeCompare(right.product));

  return { actualByProduct, monthlyActuals };
}

function buildMemberForecastLines(
  productRows: TeamMemberProducts["products"],
  reportedRows: ReportedValueRow[],
  months: FiscalMonth[],
  billRate: number,
): MemberForecastLine[] {
  const lineMap = new Map<string, { product_id: number; product: string; bucket_id: number; bucket: string }>();
  for (const row of productRows) {
    lineMap.set(memberForecastLineKey(row.product_id, row.bucket_id), {
      product_id: row.product_id,
      product: row.product,
      bucket_id: row.bucket_id,
      bucket: row.bucket,
    });
  }
  for (const row of reportedRows) {
    lineMap.set(memberForecastLineKey(row.product_id, row.bucket_id), {
      product_id: row.product_id,
      product: row.product,
      bucket_id: row.bucket_id,
      bucket: row.bucket,
    });
  }

  const reportedRowByCell = new Map<string, ReportedValueRow>();
  for (const row of reportedRows) {
    reportedRowByCell.set(`${memberForecastLineKey(row.product_id, row.bucket_id)}:${row.fiscal_month_id}`, row);
  }

  return Array.from(lineMap.values())
    .sort((left, right) => left.product.localeCompare(right.product) || left.bucket.localeCompare(right.bucket))
    .map((line) => {
      const cells = months.map((month) => {
        const sourceRow = reportedRowByCell.get(`${memberForecastLineKey(line.product_id, line.bucket_id)}:${month.id}`);
        const forecast = sourceRow?.forecast_hours ?? 0;
        const actual = sourceRow?.actual_hours ?? 0;
        const forecastCost = roundMoney(forecast * billRate);
        const actualCost = roundMoney(actual * billRate);
        return {
          fiscal_month_id: month.id,
          label: month.label,
          forecast_hours: roundHours(forecast),
          actual_hours: roundHours(actual),
          forecast_cost: forecastCost,
          actual_cost: actualCost,
          variance_cost: roundMoney(actualCost - forecastCost),
        };
      });
      const totals = cells.reduce<MemberForecastTotals>(
        (acc, cell) => {
          acc.forecast_hours += cell.forecast_hours;
          acc.actual_hours += cell.actual_hours;
          acc.forecast_cost += cell.forecast_cost;
          acc.actual_cost += cell.actual_cost;
          acc.variance_cost += cell.variance_cost;
          return acc;
        },
        { forecast_hours: 0, actual_hours: 0, forecast_cost: 0, actual_cost: 0, variance_cost: 0 },
      );

      return {
        ...line,
        months: cells,
        totals: {
          forecast_hours: roundHours(totals.forecast_hours),
          actual_hours: roundHours(totals.actual_hours),
          forecast_cost: roundMoney(totals.forecast_cost),
          actual_cost: roundMoney(totals.actual_cost),
          variance_cost: roundMoney(totals.variance_cost),
        },
      };
    });
}

function memberForecastLineKey(productId: number, bucketId: number) {
  return `${productId}:${bucketId}`;
}

function memberForecastDraftKey(line: MemberForecastLine, cell: MemberForecastMonthCell) {
  return `${memberForecastLineKey(line.product_id, line.bucket_id)}:${cell.fiscal_month_id}`;
}

function roundHours(value: number) {
  return Math.round(value * 10) / 10;
}

function roundMoney(value: number) {
  return Math.round(value * 100) / 100;
}
