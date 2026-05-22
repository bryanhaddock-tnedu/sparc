import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { cn, formatCurrency } from "../lib/utils";

interface BudgetTrackerProps {
  title?: string;
  budget: number;
  forecastSpend: number;
  actualSpend: number;
  contextLabel?: string;
  className?: string;
}

export function BudgetTracker({
  title = "Budget Tracker",
  budget,
  forecastSpend,
  actualSpend,
  contextLabel = "Budget, forecast, and actuals",
  className,
}: BudgetTrackerProps) {
  const hasBudget = budget > 0;
  const hasForecast = forecastSpend > 0;
  const scaleMax = Math.max(budget, forecastSpend, actualSpend, 0);
  const hasBaseline = scaleMax > 0;
  const actualBaseline = hasBudget ? budget : forecastSpend;
  const actualPercent = actualBaseline > 0 ? (actualSpend / actualBaseline) * 100 : 0;
  const forecastPercent = hasBudget ? (forecastSpend / budget) * 100 : 100;
  const displayPercent = Math.round(actualPercent);
  const segments = buildTrackerSegments({ actualSpend, budget, forecastSpend, scaleMax });
  const tone = hasBudget && (actualSpend > budget || forecastSpend > budget) ? "over" : actualPercent >= 90 ? "watch" : "ok";
  const statusClassName = tone === "over" ? "text-destructive" : tone === "watch" ? "text-warning" : "text-foreground";
  const statusLabel = hasBudget && hasForecast ? `${displayPercent}% actual / ${Math.round(forecastPercent)}% forecast` : hasBaseline ? `${displayPercent}%` : "No baseline";
  const statusQualifier = hasBudget && hasForecast ? "of budget" : hasForecast ? "of forecast actualized" : "actuals";
  const ariaLabel = hasBudget
    ? `${formatCurrency(actualSpend)} actuals against ${formatCurrency(budget)} budget; ${formatCurrency(forecastSpend)} forecast`
    : `${formatCurrency(actualSpend)} actuals against ${formatCurrency(forecastSpend)} forecast; budget not set`;

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="p-4 pb-2">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
          <div>
            <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">{title}</CardTitle>
            <div className="mt-1 text-sm font-medium">{contextLabel}</div>
          </div>
          <div className={cn("numeric-cell text-xl font-semibold", statusClassName)}>
            {statusLabel}
            <span className="ml-1 text-xs font-semibold uppercase text-muted-foreground">{statusQualifier}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 p-4 pt-0">
        <div aria-label={ariaLabel} className="flex h-4 overflow-hidden rounded-full bg-muted" role="img">
          {segments.map((segment) => (
            <div
              key={`${segment.label}-${segment.start}-${segment.end}`}
              className="h-full transition-[width]"
              style={{
                backgroundColor: segment.color,
                width: `${segment.widthPercent}%`,
              }}
              title={segment.label}
            />
          ))}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] font-semibold uppercase text-muted-foreground">
          <TrackerLegend color="var(--spark-cyan)" label="Actuals" />
          <TrackerLegend color="var(--spark-navy)" label="Remaining forecast" />
          {hasBudget ? <TrackerLegend color="var(--spark-gray)" label="Remaining budget" /> : null}
          {actualSpend > forecastSpend && hasForecast ? <TrackerLegend color="var(--spark-orange)" label="Over forecast" /> : null}
          {hasBudget && Math.max(actualSpend, forecastSpend) > budget ? <TrackerLegend color="hsl(var(--destructive))" label="Over budget" /> : null}
        </div>

        <div className="grid gap-2 text-xs sm:grid-cols-3">
          <BudgetLine
            label="Budgeted"
            value={hasBudget ? formatCurrency(budget) : "Not set"}
            valueClassName={hasBudget ? "text-primary" : "text-muted-foreground"}
            color="var(--spark-gray)"
          />
          <BudgetLine
            label="Forecast"
            value={formatCurrency(forecastSpend)}
            valueClassName={hasBudget && forecastSpend > budget ? "text-destructive" : "text-primary"}
            color="var(--spark-navy)"
          />
          <BudgetLine
            label="Actuals"
            value={formatCurrency(actualSpend)}
            valueClassName={hasBudget && actualSpend > budget ? "text-destructive" : "text-primary"}
            color="var(--spark-cyan)"
          />
        </div>
      </CardContent>
    </Card>
  );
}

function BudgetLine({ color, label, value, valueClassName }: { color: string; label: string; value: string; valueClassName?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 rounded-md bg-secondary/45 px-2 py-1.5">
      <span className="flex items-center gap-1.5 text-muted-foreground">
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
        {label}
      </span>
      <span className={cn("numeric-cell font-semibold", valueClassName)}>{value}</span>
    </div>
  );
}

function TrackerLegend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

function buildTrackerSegments({
  actualSpend,
  budget,
  forecastSpend,
  scaleMax,
}: {
  actualSpend: number;
  budget: number;
  forecastSpend: number;
  scaleMax: number;
}) {
  if (scaleMax <= 0) return [];

  const hasBudget = budget > 0;
  const hasForecast = forecastSpend > 0;
  const breakpoints = Array.from(new Set([0, actualSpend, forecastSpend, budget, scaleMax].filter((value) => value >= 0))).sort(
    (left, right) => left - right,
  );

  return breakpoints.slice(1).flatMap((end, index) => {
    const start = breakpoints[index];
    if (end <= start) return [];
    return [
      {
        start,
        end,
        ...trackerSegmentStyle({ actualSpend, budget, end, forecastSpend, hasBudget, hasForecast, start }),
        widthPercent: ((end - start) / scaleMax) * 100,
      },
    ];
  });
}

function trackerSegmentStyle({
  actualSpend,
  budget,
  end,
  forecastSpend,
  hasBudget,
  hasForecast,
  start,
}: {
  actualSpend: number;
  budget: number;
  end: number;
  forecastSpend: number;
  hasBudget: boolean;
  hasForecast: boolean;
  start: number;
}) {
  if (hasBudget && start >= budget) {
    return { color: "hsl(var(--destructive))", label: "Over budget" };
  }
  if (end <= actualSpend) {
    if (hasForecast && start >= forecastSpend) {
      return { color: "var(--spark-orange)", label: "Over forecast" };
    }
    return { color: "var(--spark-cyan)", label: "Actuals" };
  }
  if (end <= forecastSpend) {
    return { color: "var(--spark-navy)", label: "Remaining forecast" };
  }
  if (hasBudget && end <= budget) {
    return { color: "var(--spark-gray)", label: "Remaining budget" };
  }
  return { color: "hsl(var(--destructive))", label: "Over budget" };
}
