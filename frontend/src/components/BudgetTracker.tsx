import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { cn, formatCurrency } from "../lib/utils";

interface BudgetTrackerProps {
  title?: string;
  budget: number;
  projectedSpend: number;
  remaining: number;
  utilizationPercent: number;
  contextLabel?: string;
  className?: string;
}

export function BudgetTracker({
  title = "Budget Tracker",
  budget,
  projectedSpend,
  remaining,
  utilizationPercent,
  contextLabel = "Projected spend to budget",
  className,
}: BudgetTrackerProps) {
  const hasBudget = budget > 0;
  const displayPercent = hasBudget ? Math.round(utilizationPercent) : 0;
  const clampedPercent = Math.max(0, Math.min(displayPercent, 100));
  const tone = utilizationPercent > 100 ? "over" : utilizationPercent >= 90 ? "watch" : "ok";
  const sliceColor = tone === "over" ? "hsl(var(--destructive))" : tone === "watch" ? "hsl(var(--warning))" : "hsl(var(--accent))";
  const remainingLabel = remaining < 0 ? "Over budget" : "Budget remaining";

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="p-4 pb-2">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
          <div>
            <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">{title}</CardTitle>
            <div className="mt-1 text-sm font-medium">{contextLabel}</div>
          </div>
          <div className={cn("numeric-cell text-xl font-semibold", tone === "over" ? "text-destructive" : "text-foreground")}>
            {hasBudget ? `${displayPercent}%` : "-"}
            <span className="ml-1 text-xs font-semibold uppercase text-muted-foreground">used</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 p-4 pt-0">
        <div
          aria-label={`${displayPercent}% budget utilization`}
          className="h-3 overflow-hidden rounded-full bg-muted"
          role="img"
        >
          <div
            className="h-full rounded-full transition-[width]"
            style={{
              width: hasBudget ? `${clampedPercent}%` : "0%",
              backgroundColor: sliceColor,
            }}
          />
        </div>

        <div className="grid gap-2 text-xs sm:grid-cols-3">
          <BudgetLine label="Projected spend" value={formatCurrency(projectedSpend)} />
          <BudgetLine label="Budget" value={hasBudget ? formatCurrency(budget) : "Not set"} />
          <BudgetLine
            label={remainingLabel}
            value={formatCurrency(Math.abs(remaining))}
            valueClassName={remaining < 0 ? "text-destructive" : "text-primary"}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function BudgetLine({ label, value, valueClassName }: { label: string; value: string; valueClassName?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 rounded-md bg-secondary/45 px-2 py-1.5">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("numeric-cell font-semibold", valueClassName)}>{value}</span>
    </div>
  );
}
