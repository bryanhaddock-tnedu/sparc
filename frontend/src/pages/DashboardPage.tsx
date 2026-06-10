import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
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
type DashboardScope = number | "entire-fy";
type MonthPeriodState = "past" | "current" | "future";

const ENTIRE_FY_SCOPE = "entire-fy";
const FISCAL_MONTHS = [
  { sequence: 1, label: "Jul" },
  { sequence: 2, label: "Aug" },
  { sequence: 3, label: "Sep" },
  { sequence: 4, label: "Oct" },
  { sequence: 5, label: "Nov" },
  { sequence: 6, label: "Dec" },
  { sequence: 7, label: "Jan" },
  { sequence: 8, label: "Feb" },
  { sequence: 9, label: "Mar" },
  { sequence: 10, label: "Apr" },
  { sequence: 11, label: "May" },
  { sequence: 12, label: "Jun" },
];

export function DashboardPage() {
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [products, setProducts] = useState<ProductSummaryRow[]>([]);
  const [workTypes, setWorkTypes] = useState<DashboardWorkTypeRow[]>([]);
  const [laborMix, setLaborMix] = useState<DashboardLaborMix | null>(null);
  const [selectedScope, setSelectedScope] = useState<DashboardScope>(() => currentFiscalMonthSequence());
  const [rankedMetric, setRankedMetric] = useState<RankedMetric>("hours");
  const [loading, setLoading] = useState(true);
  const [scopeLoading, setScopeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedFiscalYearRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fullLoad = summary === null || loadedFiscalYearRef.current !== fiscalYear;

    async function loadData() {
      setError(null);
      const scopeParams = dashboardScopeParams(selectedScope);
      const [summaryResult, productsResult, workTypeResult, laborMixResult] = await Promise.all([
        fullLoad ? api.dashboardSummary(fiscalYear) : Promise.resolve(null),
        api.dashboardProducts(fiscalYear, scopeParams),
        api.dashboardWorkTypes(fiscalYear, scopeParams),
        api.dashboardLaborMix(fiscalYear, scopeParams),
      ]);
      if (cancelled) return;
      if (summaryResult) setSummary(summaryResult);
      setProducts(productsResult);
      setWorkTypes(workTypeResult);
      setLaborMix(laborMixResult);
      loadedFiscalYearRef.current = fiscalYear;
    }

    if (fullLoad) {
      setLoading(true);
    } else {
      setScopeLoading(true);
    }
    loadData()
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load dashboard");
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setScopeLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [fiscalYear, selectedScope]);

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!summary) return null;

  const productRows = products.filter((product) => product.forecasted_hours > 0 || product.fytd_hours > 0 || product.budget_amount > 0);
  const selectedScopeLabel = dashboardScopeLabel(selectedScope);
  const showActualBars = dashboardScopeHasActuals(fiscalYear, selectedScope);

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
        <DashboardScopeControl fiscalYear={fiscalYear} selectedScope={selectedScope} onScopeChange={setSelectedScope} />
      </section>

      <div className={cn("space-y-6 transition-opacity", scopeLoading && "opacity-70")} aria-busy={scopeLoading}>
        <section className="grid gap-4 xl:grid-cols-2">
          <WorkTypeMixCard rows={workTypes} scope={selectedScope} scopeLabel={selectedScopeLabel} showActuals={showActualBars} />
          <LaborMixCard data={laborMix} scopeLabel={selectedScopeLabel} />
        </section>

        <TopProductsCard
          rows={products}
          fiscalYear={fiscalYear}
          metric={rankedMetric}
          showActuals={showActualBars}
          scopeLabel={selectedScopeLabel}
          onMetricChange={setRankedMetric}
        />

        <section className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold">Product Summary</h2>
            <p className="mt-1 text-sm text-muted-foreground">{selectedScopeLabel} product totals.</p>
          </div>
          <ProductSummaryTable rows={productRows} />
        </section>
      </div>
    </div>
  );
}

function DashboardScopeControl({
  fiscalYear,
  selectedScope,
  onScopeChange,
}: {
  fiscalYear: number;
  selectedScope: DashboardScope;
  onScopeChange: (scope: DashboardScope) => void;
}) {
  return (
    <div className="w-full overflow-x-auto py-0.5">
      <div className="grid min-w-[900px] grid-cols-[repeat(12,minmax(3.75rem,1fr))_minmax(7.5rem,1.12fr)] gap-1.5">
        {FISCAL_MONTHS.map((month) => {
          const periodState = fiscalMonthPeriodState(fiscalYear, month.sequence);
          return (
            <ScopeButton
              key={month.sequence}
              active={selectedScope === month.sequence}
              label={month.label}
              periodState={periodState}
              onClick={() => onScopeChange(month.sequence)}
            />
          );
        })}
        <ScopeButton
          active={selectedScope === ENTIRE_FY_SCOPE}
          label="Entire FY"
          wide
          onClick={() => onScopeChange(ENTIRE_FY_SCOPE)}
        />
      </div>
    </div>
  );
}

function ScopeButton({
  active,
  label,
  onClick,
  periodState,
  wide = false,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
  periodState?: MonthPeriodState;
  wide?: boolean;
}) {
  const style = scopeButtonStyle(active, periodState);

  return (
    <button
      className={cn(
        "h-8 whitespace-nowrap rounded-md border px-2.5 text-sm font-semibold transition-[background-color,border-color,box-shadow,color]",
        active && "ring-inset ring-2 ring-primary",
        wide ? "min-w-28" : "min-w-14",
      )}
      style={style}
      type="button"
      aria-pressed={active}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function WorkTypeMixCard({
  rows,
  scope,
  scopeLabel,
  showActuals,
}: {
  rows: DashboardWorkTypeRow[];
  scope: DashboardScope;
  scopeLabel: string;
  showActuals: boolean;
}) {
  const forecastTotal = rows.reduce((total, row) => total + row.forecast_hours, 0);
  const actualTotal = rows.reduce((total, row) => total + row.actual_hours, 0);
  const forecastLabel = scope === ENTIRE_FY_SCOPE ? "Forecast FY" : `Forecast ${scopeLabel}`;
  const actualLabel = scope === ENTIRE_FY_SCOPE ? "Actual FYTD" : `Actual ${scopeLabel}`;

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Work Type Mix</h2>
          <p className="mt-1 text-sm text-muted-foreground">How labor is split across Net New, Enhance, and Maintenance.</p>
        </div>
      </div>
      <div className="space-y-4">
        <StackedBar label={forecastLabel} rows={rows} total={forecastTotal} valueKey="forecast_hours" />
        {showActuals ? <StackedBar label={actualLabel} rows={rows} total={actualTotal} valueKey="actual_hours" /> : null}
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
  showActuals,
  scopeLabel,
  onMetricChange,
}: {
  rows: ProductSummaryRow[];
  fiscalYear: number;
  metric: RankedMetric;
  showActuals: boolean;
  scopeLabel: string;
  onMetricChange: (metric: RankedMetric) => void;
}) {
  const ranked = useMemo(() => {
    return [...rows].sort(
      (left, right) =>
        productMetricValue(right, "forecast", metric) - productMetricValue(left, "forecast", metric) ||
        (showActuals ? productMetricValue(right, "actual", metric) - productMetricValue(left, "actual", metric) : 0) ||
        left.product.localeCompare(right.product),
    );
  }, [rows, metric, showActuals]);
  const maxValue = Math.max(
    ...ranked.flatMap((row) =>
      showActuals ? [productMetricValue(row, "forecast", metric), productMetricValue(row, "actual", metric)] : [productMetricValue(row, "forecast", metric)],
    ),
    0,
  );

  return (
    <section className="rounded-lg border bg-card p-3">
      <div className="mb-3 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Product Ranking</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Every product ranked for FY{fiscalYear} / {scopeLabel}.
          </p>
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
            const forecastValue = productMetricValue(row, "forecast", metric);
            const actualValue = productMetricValue(row, "actual", metric);
            return (
              <Link key={row.product_id} className="block rounded-md px-2 py-2 hover:bg-secondary/60" to={`/products/${row.product_id}`}>
                <div className="mb-1 flex items-baseline justify-between gap-2">
                  <div className="min-w-0 truncate text-xs font-medium">
                    <span className="mr-1.5 inline-block w-4 text-right text-muted-foreground">{index + 1}</span>
                    {row.product}
                  </div>
                  <div className="numeric-cell shrink-0 text-xs font-semibold text-primary">
                    {metric === "hours" ? formatHours(forecastValue) : formatCurrency(forecastValue)}
                  </div>
                </div>
                <div className="space-y-1.5">
                  <ProductBucketRankingBar
                    bucketTotals={row.bucket_totals}
                    label="Forecast"
                    maxValue={maxValue}
                    metric={metric}
                    total={forecastValue}
                    valueType="forecast"
                  />
                  {showActuals ? (
                    <ProductBucketRankingBar
                      bucketTotals={row.bucket_totals}
                      label="Actual"
                      maxValue={maxValue}
                      metric={metric}
                      total={actualValue}
                      valueType="actual"
                    />
                  ) : null}
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

function ProductBucketRankingBar({
  bucketTotals,
  label,
  maxValue,
  metric,
  total,
  valueType,
}: {
  bucketTotals: ProductSummaryRow["bucket_totals"];
  label: string;
  maxValue: number;
  metric: RankedMetric;
  total: number;
  valueType: "forecast" | "actual";
}) {
  const width = maxValue > 0 && total > 0 ? Math.max((total / maxValue) * 100, 3) : 0;

  return (
    <div className="grid grid-cols-[3.8rem_1fr_4.6rem] items-center gap-2">
      <div className="text-[0.68rem] font-semibold uppercase text-muted-foreground">{label}</div>
      <div className="h-2.5 overflow-hidden rounded-full bg-muted">
        <div className="flex h-full overflow-hidden rounded-full transition-[width]" style={{ width: `${width}%` }}>
          {bucketTotals.map((bucket) => {
            const value = bucketMetricValue(bucket, valueType, metric);
            return (
              <div
                key={`${label}-${bucket.bucket_id}`}
                aria-label={`${label} ${bucket.bucket} ${metric === "hours" ? formatHours(value) : formatCurrency(value)}`}
                className="h-full"
                style={{
                  width: `${total > 0 ? (value / total) * 100 : 0}%`,
                  backgroundColor: bucketColor(bucket.bucket_code),
                }}
              />
            );
          })}
        </div>
      </div>
      <div className="numeric-cell text-right text-[0.68rem] font-semibold text-primary">
        {metric === "hours" ? formatHours(total) : formatCurrency(total)}
      </div>
    </div>
  );
}

function LaborMixCard({ data, scopeLabel }: { data: DashboardLaborMix | null; scopeLabel: string }) {
  const hireTypes = data?.hire_types ?? [];
  const roles = data?.roles ?? [];
  const hireTotal = hireTypes.reduce((total, row) => total + row.forecast_hours, 0);

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-4 flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
        <div>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Labor Mix</h2>
          <p className="mt-1 text-sm text-muted-foreground">Hire type and role composition from the {scopeLabel} labor forecast.</p>
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

function currentFiscalMonthSequence() {
  const calendarMonth = new Date().getMonth() + 1;
  return calendarMonth >= 7 ? calendarMonth - 6 : calendarMonth + 6;
}

function dashboardScopeLabel(scope: DashboardScope) {
  if (scope === ENTIRE_FY_SCOPE) return "Entire FY";
  return FISCAL_MONTHS.find((month) => month.sequence === scope)?.label ?? "Selected Month";
}

function dashboardScopeParams(scope: DashboardScope) {
  return scope === ENTIRE_FY_SCOPE ? {} : { monthSequence: scope };
}

function dashboardScopeHasActuals(fiscalYear: number, scope: DashboardScope) {
  return scope === ENTIRE_FY_SCOPE || fiscalMonthPeriodState(fiscalYear, scope) !== "future";
}

function fiscalMonthPeriodState(fiscalYear: number, sequence: number): MonthPeriodState {
  const fiscalMonth = fiscalMonthDateParts(fiscalYear, sequence);
  const today = new Date();
  const current = { year: today.getFullYear(), month: today.getMonth() + 1 };

  if (fiscalMonth.year === current.year && fiscalMonth.month === current.month) return "current";
  if (fiscalMonth.year < current.year || (fiscalMonth.year === current.year && fiscalMonth.month < current.month)) return "past";
  return "future";
}

function fiscalMonthDateParts(fiscalYear: number, sequence: number) {
  if (sequence <= 6) {
    return { year: fiscalYear - 1, month: sequence + 6 };
  }
  return { year: fiscalYear, month: sequence - 6 };
}

function scopeButtonStyle(active: boolean, periodState?: MonthPeriodState): CSSProperties {
  if (!periodState) {
    return active
      ? { backgroundColor: "var(--spark-navy)", borderColor: "var(--spark-navy)", color: "white" }
      : { backgroundColor: "white", borderColor: "hsl(var(--border))", color: "hsl(var(--foreground))" };
  }

  if (periodState === "past") {
    return {
      backgroundColor: "hsl(var(--secondary))",
      borderColor: "hsl(var(--border))",
      color: active ? "hsl(var(--foreground))" : "hsl(var(--muted-foreground))",
    };
  }

  if (periodState === "current") {
    return {
      backgroundColor: "var(--spark-lime)",
      borderColor: "var(--spark-lime)",
      color: "hsl(var(--foreground))",
    };
  }

  return {
    backgroundColor: "var(--spark-cyan)",
    borderColor: "var(--spark-cyan)",
    color: "hsl(var(--foreground))",
  };
}

function productMetricValue(row: ProductSummaryRow, valueType: "forecast" | "actual", metric: RankedMetric) {
  if (valueType === "forecast") return metric === "hours" ? row.forecasted_hours : row.forecasted_cost;
  return metric === "hours" ? row.fytd_hours : row.fytd_cost;
}

function bucketMetricValue(
  bucket: ProductSummaryRow["bucket_totals"][number],
  valueType: "forecast" | "actual",
  metric: RankedMetric,
) {
  if (valueType === "forecast") return metric === "hours" ? bucket.forecast_hours : bucket.forecast_cost;
  return metric === "hours" ? bucket.actual_hours : bucket.actual_cost;
}
