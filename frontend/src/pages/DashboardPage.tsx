import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { BudgetTracker } from "../components/BudgetTracker";
import { MetricCard } from "../components/MetricCard";
import { PageNav } from "../components/PageNav";
import { ProductSummaryTable } from "../components/ProductSummaryTable";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import { cn, formatCurrency, formatHours } from "../lib/utils";
import type { DashboardLaborMix, DashboardSummary, DashboardWorkTypeRow, ProductSummaryRow } from "../types/api";

type RankedMetric = "hours" | "cost";

export function DashboardPage() {
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [products, setProducts] = useState<ProductSummaryRow[]>([]);
  const [workTypes, setWorkTypes] = useState<DashboardWorkTypeRow[]>([]);
  const [laborMix, setLaborMix] = useState<DashboardLaborMix | null>(null);
  const [rankedMetric, setRankedMetric] = useState<RankedMetric>("hours");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    setError(null);
    const [summaryResult, productsResult, workTypeResult, laborMixResult] = await Promise.all([
      api.dashboardSummary(fiscalYear),
      api.dashboardProducts(fiscalYear),
      api.dashboardWorkTypes(fiscalYear),
      api.dashboardLaborMix(fiscalYear),
    ]);
    setSummary(summaryResult);
    setProducts(productsResult);
    setWorkTypes(workTypeResult);
    setLaborMix(laborMixResult);
  }

  useEffect(() => {
    setLoading(true);
    loadData()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load dashboard"))
      .finally(() => setLoading(false));
  }, [fiscalYear]);

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!summary) return null;

  const productRows = products.filter((product) => product.forecasted_hours > 0 || product.fytd_hours > 0 || product.budget_amount > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {fiscalYearLabel} product labor forecast and actuals ({fiscalYearRangeLabel}).
          </p>
        </div>
        <PageNav current="dashboard" />
      </div>

      <section className="space-y-3">
        <BudgetTracker
          budget={summary.budget_amount}
          forecastSpend={summary.forecasted_cost}
          actualSpend={summary.fytd_cost}
          contextLabel="All products budget, forecast, and actuals"
        />
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard density="compact" label="Forecast $" value={formatCurrency(summary.forecasted_cost)} />
          <MetricCard density="compact" label="Actual $" value={formatCurrency(summary.fytd_cost)} />
          <MetricCard density="compact" label="Remaining $" value={formatCurrency(summary.remaining_cost)} tone="good" />
          <MetricCard density="compact" label="Actual Hrs" value={formatHours(summary.fytd_hours)} />
          <MetricCard density="compact" label="Forecast Hrs" value={formatHours(summary.forecasted_hours)} />
          <MetricCard
            density="compact"
            label="Variance $"
            value={formatCurrency(summary.variance_cost)}
            tone={summary.variance_cost > 0 ? "warn" : "good"}
          />
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <WorkTypeMixCard rows={workTypes} />
        <LaborMixCard data={laborMix} />
      </section>

      <TopProductsCard rows={products} fiscalYear={fiscalYear} metric={rankedMetric} onMetricChange={setRankedMetric} />

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Product Summary</h2>
        <ProductSummaryTable rows={productRows} />
      </section>
    </div>
  );
}

function WorkTypeMixCard({ rows }: { rows: DashboardWorkTypeRow[] }) {
  const forecastTotal = rows.reduce((total, row) => total + row.forecast_hours, 0);
  const actualTotal = rows.reduce((total, row) => total + row.actual_hours, 0);

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Work Type Mix</h2>
          <p className="mt-1 text-sm text-muted-foreground">How labor is split across Net New, Enhance, and Maintenance.</p>
        </div>
      </div>
      <div className="space-y-4">
        <StackedBar label="Forecast FY" rows={rows} total={forecastTotal} valueKey="forecast_hours" />
        <StackedBar label="Actual FYTD" rows={rows} total={actualTotal} valueKey="actual_hours" />
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {rows.map((row) => (
          <div key={row.bucket_id} className="rounded-md bg-secondary/50 px-3 py-2">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: bucketColor(row.bucket_code) }} />
              {row.bucket}
            </div>
            <div className="numeric-cell mt-1 text-lg font-semibold text-primary">{formatHours(row.forecast_hours)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function TopProductsCard({
  rows,
  fiscalYear,
  metric,
  onMetricChange,
}: {
  rows: ProductSummaryRow[];
  fiscalYear: number;
  metric: RankedMetric;
  onMetricChange: (metric: RankedMetric) => void;
}) {
  const ranked = useMemo(() => {
    const valueKey = metric === "hours" ? "forecasted_hours" : "forecasted_cost";
    return [...rows].sort((left, right) => right[valueKey] - left[valueKey] || left.product.localeCompare(right.product));
  }, [rows, metric]);
  const maxValue = Math.max(...ranked.map((row) => (metric === "hours" ? row.forecasted_hours : row.forecasted_cost)), 0);

  return (
    <section className="rounded-lg border bg-card p-3">
      <div className="mb-3 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Product Ranking</h2>
          <p className="mt-1 text-sm text-muted-foreground">Every product ranked for FY{fiscalYear}.</p>
        </div>
        <div className="flex rounded-md border bg-background p-1">
          <ToggleButton active={metric === "hours"} onClick={() => onMetricChange("hours")}>
            Hours
          </ToggleButton>
          <ToggleButton active={metric === "cost"} onClick={() => onMetricChange("cost")}>
            Cost
          </ToggleButton>
        </div>
      </div>
      <div className="grid gap-1.5 md:grid-cols-2 xl:grid-cols-3">
        {ranked.length ? (
          ranked.map((row, index) => {
            const value = metric === "hours" ? row.forecasted_hours : row.forecasted_cost;
            return (
              <Link key={row.product_id} className="block rounded-md px-2 py-1.5 hover:bg-secondary/60" to={`/products/${row.product_id}`}>
                <div className="mb-1 flex items-baseline justify-between gap-2">
                  <div className="min-w-0 truncate text-xs font-medium">
                    <span className="mr-1.5 inline-block w-4 text-right text-muted-foreground">{index + 1}</span>
                    {row.product}
                  </div>
                  <div className="numeric-cell shrink-0 text-xs font-semibold text-primary">
                    {metric === "hours" ? formatHours(value) : formatCurrency(value)}
                  </div>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-[width]"
                    style={{ width: `${maxValue > 0 ? Math.max((value / maxValue) * 100, 3) : 0}%` }}
                  />
                </div>
              </Link>
            );
          })
        ) : (
          <div className="rounded-md bg-secondary/50 p-4 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
            No product labor has been forecasted yet.
          </div>
        )}
      </div>
    </section>
  );
}

function LaborMixCard({ data }: { data: DashboardLaborMix | null }) {
  const hireTypes = data?.hire_types ?? [];
  const roles = data?.roles ?? [];
  const hireTotal = hireTypes.reduce((total, row) => total + row.forecast_hours, 0);

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-4 flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Labor Mix</h2>
          <p className="mt-1 text-sm text-muted-foreground">Hire type and role composition from the current labor forecast.</p>
        </div>
      </div>
      <div className="space-y-4">
        <div className="space-y-3">
          {hireTypes.length ? (
            hireTypes.map((row, index) => (
              <div key={row.employment_type}>
                <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                  <span className="font-medium">{row.employment_type}</span>
                  <span className="numeric-cell text-muted-foreground">{hireTotal ? Math.round((row.forecast_hours / hireTotal) * 100) : 0}%</span>
                </div>
                <div className="h-3 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full transition-[width]"
                    style={{
                      width: `${hireTotal ? Math.max((row.forecast_hours / hireTotal) * 100, 3) : 0}%`,
                      backgroundColor: index === 0 ? "var(--spark-navy)" : "var(--spark-cyan)",
                    }}
                  />
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-md bg-secondary/50 p-4 text-sm text-muted-foreground">No labor mix data yet.</div>
          )}
        </div>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {roles.map((row) => (
            <div key={row.role} className="rounded-md bg-secondary/50 px-3 py-2">
              <div className="truncate text-xs font-semibold uppercase text-muted-foreground">{row.role}</div>
              <div className="numeric-cell mt-1 text-lg font-semibold text-primary">{formatHours(row.forecast_hours)}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function StackedBar({
  label,
  rows,
  total,
  valueKey,
}: {
  label: string;
  rows: DashboardWorkTypeRow[];
  total: number;
  valueKey: "forecast_hours" | "actual_hours";
}) {
  return (
    <div>
      <div className="mb-1 flex justify-between gap-3 text-sm">
        <span className="font-medium">{label}</span>
        <span className="numeric-cell text-muted-foreground">{formatHours(total)}</span>
      </div>
      <div className="flex h-4 overflow-hidden rounded-full bg-muted">
        {rows.map((row) => {
          const value = row[valueKey];
          return (
            <div
              key={`${label}-${row.bucket_id}`}
              aria-label={`${row.bucket} ${formatHours(value)}`}
              className="h-full transition-[width]"
              style={{
                width: `${total > 0 ? (value / total) * 100 : 0}%`,
                backgroundColor: bucketColor(row.bucket_code),
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

function ToggleButton({ active, children, onClick }: { active: boolean; children: string; onClick: () => void }) {
  return (
    <button
      className={cn(
        "rounded px-3 py-1.5 text-sm font-medium",
        active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
      )}
      type="button"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function bucketColor(code: string) {
  if (code === "NET_NEW") return "var(--spark-cyan)";
  if (code === "ENHANCE") return "var(--spark-lime)";
  return "var(--spark-orange)";
}
