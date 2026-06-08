import { Play, Terminal } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import { PageNav } from "../components/PageNav";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import type { SystemScanResult } from "../types/api";

export function SystemScanPage({ embedded = false }: { embedded?: boolean } = {}) {
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [budgetWarningPercent, setBudgetWarningPercent] = useState("85");
  const [memberForecastLimitHours, setMemberForecastLimitHours] = useState("10");
  const [workingDays, setWorkingDays] = useState("7");
  const [scanResult, setScanResult] = useState<SystemScanResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runScan() {
    setRunning(true);
    setError(null);
    try {
      const result = await api.systemScan(fiscalYear, {
        budgetWarningPercent: numericValue(budgetWarningPercent, 85),
        memberForecastLimitHours: numericValue(memberForecastLimitHours, 10),
        workingDays: numericValue(workingDays, 7),
      });
      setScanResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run system scan");
    } finally {
      setRunning(false);
    }
  }

  const consoleOutput =
    scanResult?.output ??
    [
      "SPARC SYSTEM SCAN",
      `Fiscal year: ${fiscalYearLabel}`,
      "",
      "Ready.",
      "Click Run System Scan to inspect forecast gaps, recent actual-hour activity, budget pressure, and current-month forecast overruns.",
    ].join("\n");

  return (
    <div className="space-y-5">
      <section className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end">
        <div>
          {embedded ? <h2 className="text-xl font-semibold">System Scan</h2> : <h1 className="text-2xl font-semibold">System Scan</h1>}
          <p className="mt-1 text-sm text-muted-foreground">
            Read-only operational checks for {fiscalYearLabel} ({fiscalYearRangeLabel}).
          </p>
        </div>
        {embedded ? null : <PageNav current="admin" />}
      </section>

      {error ? <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}

      <Card>
        <CardHeader className="gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Scan Controls
            </CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">Current parameters apply only to this scan run.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 lg:w-[560px]">
            <Field label="Budget alert %">
              <Input
                min={0}
                max={200}
                step={5}
                type="number"
                value={budgetWarningPercent}
                onChange={(event) => setBudgetWarningPercent(event.target.value)}
              />
            </Field>
            <Field label="Forecast buffer hours">
              <Input
                min={0}
                max={500}
                step={1}
                type="number"
                value={memberForecastLimitHours}
                onChange={(event) => setMemberForecastLimitHours(event.target.value)}
              />
            </Field>
            <Field label="Actuals lookback working days">
              <Input min={1} max={30} step={1} type="number" value={workingDays} onChange={(event) => setWorkingDays(event.target.value)} />
            </Field>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-muted-foreground">
              {scanResult ? `Last run: ${formatTimestamp(scanResult.generated_at)}` : "No scan has been run in this session."}
            </div>
            <Button onClick={runScan} disabled={running}>
              <Play className={`h-4 w-4 ${running ? "animate-pulse" : ""}`} />
              {running ? "Scanning" : "Run System Scan"}
            </Button>
          </div>
          <pre className="max-h-[560px] min-h-[420px] overflow-auto whitespace-pre-wrap rounded-md border border-slate-800 bg-slate-950 p-4 font-mono text-[12px] leading-5 text-slate-100 shadow-inner">
            {consoleOutput}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
      <span>{label}</span>
      {children}
    </label>
  );
}

function numericValue(value: string, fallback: number) {
  if (!value.trim()) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
