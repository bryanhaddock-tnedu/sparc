import { Plug, RefreshCw, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { BudgetTracker } from "../components/BudgetTracker";
import { MetricCard } from "../components/MetricCard";
import { ProductSummaryTable } from "../components/ProductSummaryTable";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import { formatCurrency, formatHours } from "../lib/utils";
import type { DashboardSummary, ProductSummaryRow, UnmappedProduct, UnmappedUser } from "../types/api";

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [products, setProducts] = useState<ProductSummaryRow[]>([]);
  const [unmappedUsers, setUnmappedUsers] = useState<UnmappedUser[]>([]);
  const [unmappedProducts, setUnmappedProducts] = useState<UnmappedProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    setError(null);
    const [summaryResult, productsResult, usersResult, productsUnmappedResult] = await Promise.all([
      api.dashboardSummary(),
      api.dashboardProducts(),
      api.unmappedUsers(),
      api.unmappedProducts(),
    ]);
    setSummary(summaryResult);
    setProducts(productsResult);
    setUnmappedUsers(usersResult);
    setUnmappedProducts(productsUnmappedResult);
  }

  useEffect(() => {
    loadData()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load dashboard"))
      .finally(() => setLoading(false));
  }, []);

  async function runSync() {
    setSyncing(true);
    try {
      await api.syncMockJiraRovo();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run sync");
    } finally {
      setSyncing(false);
    }
  }

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!summary) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">FY{api.fiscalYear} product labor forecast and actuals.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline">
            <Link to="/team">
              <Users className="h-4 w-4" />
              Team
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/integrations">
              <Plug className="h-4 w-4" />
              Jira/Rovo
            </Link>
          </Button>
          <Button onClick={runSync} disabled={syncing}>
            <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
            Mock Jira/Rovo Sync
          </Button>
        </div>
      </div>

      <section className="space-y-3">
        <BudgetTracker
          budget={summary.budget_amount}
          projectedSpend={summary.projected_spend}
          remaining={summary.budget_remaining}
          utilizationPercent={summary.budget_utilization_percent}
          contextLabel="All products projected spend"
        />
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard label="FY Forecasted Cost" value={formatCurrency(summary.forecasted_cost)} />
          <MetricCard label="FYTD Actualized Cost" value={formatCurrency(summary.fytd_cost)} />
          <MetricCard label="Remaining Forecasted Cost" value={formatCurrency(summary.remaining_cost)} tone="good" />
          <MetricCard label="FYTD Actualized Hours" value={formatHours(summary.fytd_hours)} />
          <MetricCard label="Forecasted Hours" value={formatHours(summary.forecasted_hours)} />
          <MetricCard
            label="Cost Variance"
            value={formatCurrency(summary.variance_cost)}
            tone={summary.variance_cost > 0 ? "warn" : "good"}
          />
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
          <h2 className="text-lg font-semibold">Product Summary</h2>
          <div className="text-sm text-muted-foreground">
            {unmappedUsers.length + unmappedProducts.length} unmapped Jira/Rovo references
          </div>
        </div>
        <ProductSummaryTable rows={products} />
      </section>
    </div>
  );
}
