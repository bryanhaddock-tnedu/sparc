import { ArrowLeft, RotateCcw, Save } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Link, useParams } from "react-router-dom";

import { BudgetTracker } from "../components/BudgetTracker";
import { MetricCard } from "../components/MetricCard";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { api } from "../lib/api";
import { formatCurrency, formatHours } from "../lib/utils";
import type { BucketTable, BucketTableRow, MonthCell, ProductBucketTables, ProductSummary } from "../types/api";

const PIE_COLORS = ["#2CCCD3", "#D2D755", "#E87722", "#5E7975"];

export function ProductDetailPage() {
  const params = useParams();
  const productId = Number(params.productId);
  const [summary, setSummary] = useState<ProductSummary | null>(null);
  const [tables, setTables] = useState<ProductBucketTables | null>(null);
  const [distribution, setDistribution] = useState<{ bucket: string; hours: number }[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    const [summaryResult, distributionResult, tablesResult] = await Promise.all([
      api.productSummary(productId),
      api.bucketDistribution(productId),
      api.productBucketTables(productId),
    ]);
    setSummary(summaryResult);
    setDistribution(distributionResult.map((row) => ({ bucket: row.bucket, hours: row.hours })));
    setTables(tablesResult);
    setDrafts({});
  }

  useEffect(() => {
    if (!Number.isFinite(productId)) return;
    loadData()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load product"))
      .finally(() => setLoading(false));
  }, [productId]);

  function updateDraft(bucket: BucketTable, row: BucketTableRow, cell: MonthCell, value: string) {
    const key = draftKey(bucket, row, cell);
    setDrafts((current) => {
      const next = { ...current };
      if (value === String(cell.forecast_hours)) {
        delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
    setSaveMessage(null);
  }

  async function saveDrafts() {
    if (!tables || dirtyEntries.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      await api.upsertForecastBatch(
        dirtyEntries.map(({ bucket, row, cell, value }) => ({
          product_id: productId,
          team_member_id: row.team_member_id,
          bucket_id: bucket.bucket_id,
          fiscal_month_id: cell.fiscal_month_id,
          hours: value,
        })),
      );
      setSaveMessage(`${dirtyEntries.length} forecast ${dirtyEntries.length === 1 ? "cell" : "cells"} saved.`);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save forecasts");
    } finally {
      setSaving(false);
    }
  }

  const dirtyEntries = tables ? collectDirtyEntries(tables, drafts) : [];
  const draftCount = Object.keys(drafts).length;
  const hasInvalidDrafts = draftCount !== dirtyEntries.length;

  function discardDrafts() {
    setDrafts({});
    setSaveMessage(null);
  }

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!summary || !tables) return null;

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/">
          <ArrowLeft className="h-4 w-4" />
          Dashboard
        </Link>
      </Button>

      <section className="flex flex-col justify-between gap-4 border-b pb-5 lg:flex-row lg:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold">{summary.product.name}</h1>
            <Badge>{summary.product.jira_space_key ?? "No Jira Space"}</Badge>
            <Badge className={summary.product.is_active ? "border-primary/40 text-primary" : "border-muted text-muted-foreground"}>
              {summary.product.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
          {summary.product.description ? (
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{summary.product.description}</p>
          ) : null}
        </div>
      </section>

      <section className="space-y-3">
        <BudgetTracker
          budget={summary.budget_amount}
          projectedSpend={summary.projected_spend}
          remaining={summary.budget_remaining}
          utilizationPercent={summary.budget_utilization_percent}
          contextLabel={`${summary.product.name} projected spend`}
        />
        <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
          <div className="rounded-lg border bg-card p-4">
            <h2 className="mb-3 text-sm font-semibold uppercase text-muted-foreground">FYTD Actualized Hours</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={distribution} dataKey="hours" nameKey="bucket" innerRadius={56} outerRadius={88} paddingAngle={2}>
                    {distribution.map((entry, index) => (
                      <Cell key={entry.bucket} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => `${formatHours(value)} hrs`} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <MetricCard label="Actualized Hours FYTD" value={formatHours(summary.fytd_hours)} />
            <MetricCard label="Forecasted Hours FY" value={formatHours(summary.forecasted_hours)} />
            <MetricCard label="Remaining Hours" value={formatHours(summary.remaining_hours)} tone="good" />
            <MetricCard label="Actualized Cost FYTD" value={formatCurrency(summary.fytd_cost)} />
            <MetricCard label="Forecasted Cost FY" value={formatCurrency(summary.forecasted_cost)} />
            <MetricCard label="Remaining Cost" value={formatCurrency(summary.remaining_cost)} tone="good" />
          </div>
        </div>
      </section>

      <section className="space-y-5">
        <div className="flex flex-col justify-between gap-3 rounded-lg border bg-card p-3 sm:flex-row sm:items-center">
          <div>
            <div className="text-sm font-medium">Forecast edit session</div>
            <div className="text-sm text-muted-foreground">
              {draftCount ? `${draftCount} unsaved ${draftCount === 1 ? "cell" : "cells"}` : "No unsaved changes"}
              {hasInvalidDrafts ? " / Fix invalid values before saving" : ""}
              {saveMessage ? ` / ${saveMessage}` : ""}
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={discardDrafts} disabled={!draftCount || saving}>
              <RotateCcw className="h-4 w-4" />
              Discard
            </Button>
            <Button onClick={saveDrafts} disabled={!dirtyEntries.length || hasInvalidDrafts || saving}>
              <Save className="h-4 w-4" />
              {saving ? "Saving" : "Save Changes"}
            </Button>
          </div>
        </div>
        {tables.buckets.map((bucket) => (
          <BucketSection key={bucket.bucket_id} bucket={bucket} drafts={drafts} onDraftChange={updateDraft} />
        ))}
      </section>
    </div>
  );
}

function BucketSection({
  bucket,
  drafts,
  onDraftChange,
}: {
  bucket: BucketTable;
  drafts: Record<string, string>;
  onDraftChange: (bucket: BucketTable, row: BucketTableRow, cell: MonthCell, value: string) => void;
}) {
  const monthlyTotals =
    bucket.rows[0]?.months.map((month, index) => {
      return bucket.rows.reduce(
        (acc, row) => {
          const cell = row.months[index];
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
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{bucket.name}</h2>
        <div className="numeric-cell text-sm text-muted-foreground">
          {formatHours(bucket.totals.forecast_hours)} forecast / {formatHours(bucket.totals.actual_hours)} actual
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="min-w-[1560px] border-collapse text-sm">
            <thead>
              <tr className="border-b bg-secondary/60">
                <th className="sticky left-0 z-10 w-48 bg-secondary px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                  Team Member
                </th>
                <th className="sticky left-48 z-10 w-32 bg-secondary px-3 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                  Metric
                </th>
                {bucket.rows[0]?.months.map((month) => (
                  <th key={month.fiscal_month_id} className="w-24 px-2 py-3 text-right text-xs font-semibold uppercase text-muted-foreground">
                    {month.label}
                  </th>
                ))}
                <th className="w-28 px-2 py-3 text-right text-xs font-semibold uppercase text-muted-foreground">FY Total</th>
              </tr>
            </thead>
            <tbody>
              {bucket.rows.map((row) => (
                <Fragment key={row.team_member_id}>
                  <tr className="border-t align-middle">
                    <td rowSpan={4} className="sticky left-0 z-10 bg-card px-3 py-3 align-top">
                      <Link className="font-medium text-primary hover:underline" to={`/team-members/${row.team_member_id}`}>
                        {row.team_member}
                      </Link>
                      <div className="numeric-cell mt-1 text-xs text-muted-foreground">{formatCurrency(row.bill_rate)}/hr</div>
                    </td>
                    <MetricLabel label="Forecast" />
                    {row.months.map((cell) => (
                      <td key={cell.fiscal_month_id} className="px-2 py-1.5">
                        <ForecastInput
                          bucket={bucket}
                          row={row}
                          cell={cell}
                          value={drafts[draftKey(bucket, row, cell)] ?? String(cell.forecast_hours)}
                          dirty={drafts[draftKey(bucket, row, cell)] !== undefined}
                          onChange={(value) => onDraftChange(bucket, row, cell, value)}
                        />
                      </td>
                    ))}
                    <ValueCell value={formatHours(row.totals.forecast_hours)} strong />
                  </tr>
                  <tr>
                    <MetricLabel label="Actual" muted />
                    {row.months.map((cell) => (
                      <ValueCell key={cell.fiscal_month_id} value={formatHours(cell.actual_hours)} muted />
                    ))}
                    <ValueCell value={formatHours(row.totals.actual_hours)} muted strong />
                  </tr>
                  <tr>
                    <MetricLabel label="Forecast cost" />
                    {row.months.map((cell) => (
                      <ValueCell key={cell.fiscal_month_id} value={formatCurrency(cell.forecast_cost)} />
                    ))}
                    <ValueCell value={formatCurrency(row.totals.forecast_cost)} strong />
                  </tr>
                  <tr className="border-b">
                    <MetricLabel label="Variance" />
                    {row.months.map((cell) => (
                      <ValueCell
                        key={cell.fiscal_month_id}
                        value={formatCurrency(cell.variance_cost)}
                        className={cell.variance_cost > 0 ? "text-destructive" : "text-primary"}
                      />
                    ))}
                    <ValueCell
                      value={formatCurrency(row.totals.variance_cost)}
                      className={row.totals.variance_cost > 0 ? "text-destructive" : "text-primary"}
                      strong
                    />
                  </tr>
                </Fragment>
              ))}
              <tr className="border-t bg-secondary/50 font-semibold">
                <td rowSpan={4} className="sticky left-0 z-10 bg-secondary px-3 py-3 align-top">
                  Bucket Total
                </td>
                <MetricLabel label="Forecast" total />
                {monthlyTotals.map((totals) => (
                  <ValueCell key={totals.fiscalMonthId} value={formatHours(totals.forecast)} total strong />
                ))}
                <ValueCell value={formatHours(bucket.totals.forecast_hours)} total strong />
              </tr>
              <tr className="bg-secondary/50 font-semibold">
                <MetricLabel label="Actual" muted total />
                {monthlyTotals.map((totals) => (
                  <ValueCell key={totals.fiscalMonthId} value={formatHours(totals.actual)} muted total strong />
                ))}
                <ValueCell value={formatHours(bucket.totals.actual_hours)} muted total strong />
              </tr>
              <tr className="bg-secondary/50 font-semibold">
                <MetricLabel label="Forecast cost" total />
                {monthlyTotals.map((totals) => (
                  <ValueCell key={totals.fiscalMonthId} value={formatCurrency(totals.cost)} total strong />
                ))}
                <ValueCell value={formatCurrency(bucket.totals.forecast_cost)} total strong />
              </tr>
              <tr className="bg-secondary/50 font-semibold">
                <MetricLabel label="Variance" total />
                {monthlyTotals.map((totals) => (
                  <ValueCell
                    key={totals.fiscalMonthId}
                    value={formatCurrency(totals.variance)}
                    className={totals.variance > 0 ? "text-destructive" : "text-primary"}
                    total
                    strong
                  />
                ))}
                <ValueCell
                  value={formatCurrency(bucket.totals.variance_cost)}
                  className={bucket.totals.variance_cost > 0 ? "text-destructive" : "text-primary"}
                  total
                  strong
                />
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function ForecastInput({
  bucket,
  row,
  cell,
  value,
  dirty,
  onChange,
}: {
  bucket: BucketTable;
  row: BucketTableRow;
  cell: MonthCell;
  value: string;
  dirty: boolean;
  onChange: (value: string) => void;
}) {
  const numericValue = Number(value);
  const invalid = value !== "" && (!Number.isFinite(numericValue) || numericValue < 0);
  return (
    <Input
      aria-label={`${bucket.name} ${row.team_member} ${cell.label} forecast hours`}
      className={`numeric-cell h-8 px-2 text-right ${dirty ? "border-primary bg-primary/5" : ""} ${invalid ? "border-destructive" : ""}`}
      inputMode="decimal"
      pattern="[0-9]*"
      type="text"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

function MetricLabel({ label, muted, total }: { label: string; muted?: boolean; total?: boolean }) {
  return (
    <td
      className={`sticky left-48 z-10 px-3 py-2 text-xs font-semibold uppercase ${
        total ? "bg-secondary" : "bg-card"
      } ${muted ? "text-muted-foreground" : "text-foreground"}`}
    >
      {label}
    </td>
  );
}

function ValueCell({
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
    <td className={`numeric-cell px-2 py-2 text-right text-sm ${total ? "bg-secondary/50" : ""} ${muted ? "text-muted-foreground" : ""}`}>
      <span className={`${strong ? "font-semibold" : "font-medium"} ${className ?? ""}`}>{value}</span>
    </td>
  );
}

function draftKey(bucket: BucketTable, row: BucketTableRow, cell: MonthCell) {
  return `${bucket.bucket_id}:${row.team_member_id}:${cell.fiscal_month_id}`;
}

function collectDirtyEntries(tables: ProductBucketTables, drafts: Record<string, string>) {
  const entries: { bucket: BucketTable; row: BucketTableRow; cell: MonthCell; value: number }[] = [];
  for (const bucket of tables.buckets) {
    for (const row of bucket.rows) {
      for (const cell of row.months) {
        const draft = drafts[draftKey(bucket, row, cell)];
        if (draft === undefined) continue;
        const value = Number(draft);
        if (!Number.isFinite(value) || value < 0) continue;
        entries.push({ bucket, row, cell, value });
      }
    }
  }
  return entries;
}
