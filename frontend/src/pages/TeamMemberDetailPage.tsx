import { Pencil, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { BudgetTracker } from "../components/BudgetTracker";
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
import type { ReportedValueRow, TeamMember, TeamMemberProducts } from "../types/api";

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ProfileFormState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  async function loadData() {
    const [productsResult, reportedRowsResult] = await Promise.all([
      api.teamMemberProducts(teamMemberId, fiscalYear),
      api.reportedValues({ team_member_id: teamMemberId }, fiscalYear),
    ]);
    setData(productsResult);
    setReportedRows(reportedRowsResult);
  }

  useEffect(() => {
    setLoading(true);
    loadData()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load team member"))
      .finally(() => setLoading(false));
  }, [teamMemberId, fiscalYear]);

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!data) return null;

  const member = data.team_member;
  const forecastHours = data.products.reduce((total, row) => total + row.forecast_hours, 0);
  const actualHours = data.products.reduce((total, row) => total + row.actual_hours, 0);
  const forecastCost = data.products.reduce((total, row) => total + row.forecast_cost, 0);
  const actualCost = data.products.reduce((total, row) => total + row.actual_cost, 0);

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

      <section className="grid gap-4 lg:grid-cols-[360px_1fr]">
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
        <div className="grid gap-3 sm:grid-cols-2">
          <BudgetTracker
            className="sm:col-span-2"
            budget={0}
            forecastSpend={forecastCost}
            actualSpend={actualCost}
            contextLabel="Member forecast and actuals across supported products"
          />
          <MetricCard label="Forecast Hours" value={formatHours(forecastHours)} />
          <MetricCard label="Actual Hours" value={formatHours(actualHours)} />
          <MetricCard label="Forecast Cost" value={formatCurrency(forecastCost)} />
          <MetricCard label="Actual Cost" value={formatCurrency(actualCost)} />
        </div>
      </section>

      <ReportedValuesTable rows={reportedRows} showProduct />

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

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}
