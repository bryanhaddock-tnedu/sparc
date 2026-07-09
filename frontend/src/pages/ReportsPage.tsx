import { Download, FileSpreadsheet } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useFiscalYear } from "../lib/fiscalYear";
import { cn, formatCurrency, formatHours } from "../lib/utils";
import type {
  LaborCostReport,
  LaborCostReportDimension,
  LaborCostReportMetric,
  LaborCostReportOptionalDimension,
  LaborCostReportRow,
  LaborCostReportSort,
} from "../types/api";

const DIMENSION_OPTIONS: Array<{ key: LaborCostReportDimension; label: string }> = [
  { key: "person", label: "Person" },
  { key: "team", label: "Team" },
  { key: "product", label: "Product" },
  { key: "bucket", label: "Bucket" },
];

const METRIC_OPTIONS: Array<{ key: LaborCostReportMetric; label: string }> = [
  { key: "forecast_cost", label: "Forecast Cost" },
  { key: "actual_cost", label: "Actual Cost" },
  { key: "variance_cost", label: "Variance Cost" },
  { key: "forecast_hours", label: "Forecast Hours" },
  { key: "actual_hours", label: "Actual Hours" },
];

export function ReportsPage() {
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const { status } = useAuth();
  const canViewNamedPeople = status?.capabilities.can_view_named_people === true;
  const [leadDimension, setLeadDimension] = useState<LaborCostReportDimension>(() => (canViewNamedPeople ? "person" : "product"));
  const [secondDimension, setSecondDimension] = useState<LaborCostReportOptionalDimension>(() => (canViewNamedPeople ? "product" : "bucket"));
  const [thirdDimension, setThirdDimension] = useState<LaborCostReportOptionalDimension>(() => (canViewNamedPeople ? "bucket" : "none"));
  const [sortMetric, setSortMetric] = useState<LaborCostReportSort>("forecast_cost");
  const [report, setReport] = useState<LaborCostReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const reportParams = useMemo(
    () => ({
      lead: leadDimension,
      second: secondDimension,
      third: thirdDimension,
      sort: sortMetric,
    }),
    [leadDimension, secondDimension, sortMetric, thirdDimension],
  );
  const sortOptions = useMemo(
    () => [...activeDimensionOptions(leadDimension, secondDimension, thirdDimension), ...METRIC_OPTIONS],
    [leadDimension, secondDimension, thirdDimension],
  );
  const dimensionOptions = useMemo(
    () => DIMENSION_OPTIONS.filter((option) => canViewNamedPeople || option.key !== "person"),
    [canViewNamedPeople],
  );
  const optionalDimensionOptions = useMemo(
    () => [{ key: "none" as const, label: "None" }, ...dimensionOptions],
    [dimensionOptions],
  );

  useEffect(() => {
    if (canViewNamedPeople) return;
    if (leadDimension === "person") setLeadDimension("product");
    if (secondDimension === "person") setSecondDimension("bucket");
    if (thirdDimension === "person") setThirdDimension("none");
  }, [canViewNamedPeople, leadDimension, secondDimension, thirdDimension]);

  useEffect(() => {
    if (!sortOptions.some((option) => option.key === sortMetric)) {
      setSortMetric("forecast_cost");
    }
  }, [sortMetric, sortOptions]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .laborCostReport(fiscalYear, reportParams)
      .then(setReport)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load labor cost report"))
      .finally(() => setLoading(false));
  }, [fiscalYear, reportParams]);

  const exportReport = useCallback(async () => {
    setExporting(true);
    setExportError(null);
    try {
      const { blob, filename } = await api.exportLaborCostReport(fiscalYear, reportParams);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Unable to export labor cost report");
    } finally {
      setExporting(false);
    }
  }, [fiscalYear, reportParams]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-normal text-foreground">Reports</h1>
          <p className="mt-1 text-muted-foreground">
            Enterprise labor cost rollups for {fiscalYearLabel} ({fiscalYearRangeLabel}).
          </p>
        </div>
        <PageNav current="reports" />
      </div>

      <div className="border-t" />

      <Card>
        <CardHeader className="gap-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-xl">
                <FileSpreadsheet className="h-5 w-5" />
                Labor Cost Report
              </CardTitle>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                Pivot forecast and actual cost by Person, Team, Product, and Bucket. Product and Person values link back to their detail pages.
              </p>
            </div>
            <Button onClick={() => void exportReport()} disabled={exporting || loading || !report}>
              <Download className="h-4 w-4" />
              {exporting ? "Exporting" : "Export XLSX"}
            </Button>
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <DimensionSelect
              label="Lead Column"
              value={leadDimension}
              options={dimensionOptions}
              onChange={(value) => setLeadDimension(value as LaborCostReportDimension)}
            />
            <DimensionSelect
              label="Then"
              value={secondDimension}
              options={optionalDimensionOptions}
              onChange={(value) => setSecondDimension(value as LaborCostReportOptionalDimension)}
            />
            <DimensionSelect
              label="Then"
              value={thirdDimension}
              options={optionalDimensionOptions}
              onChange={(value) => setThirdDimension(value as LaborCostReportOptionalDimension)}
            />
            <DimensionSelect label="Sort By" value={sortMetric} options={sortOptions} onChange={(value) => setSortMetric(value as LaborCostReportSort)} />
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {exportError ? <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">{exportError}</div> : null}
          {loading ? <LoadingBlock /> : error ? <ErrorBlock message={error} /> : report ? <LaborCostReportTable report={report} /> : null}
        </CardContent>
      </Card>
    </div>
  );
}

function LaborCostReportTable({ report }: { report: LaborCostReport }) {
  const rows = report.rows;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <ReportMetric label="Forecast Cost" value={formatCurrency(report.totals.forecast_cost)} />
        <ReportMetric label="Actual Cost" value={formatCurrency(report.totals.actual_cost)} />
        <ReportMetric label="Variance Cost" value={formatCurrency(report.totals.variance_cost)} tone={report.totals.variance_cost > 0 ? "warn" : "default"} />
        <ReportMetric label="Rows" value={formatHours(rows.length)} />
      </div>

      <div className="overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            <TableRow className="bg-secondary/70 hover:bg-secondary/70">
              {report.dimensions.map((dimension) => (
                <TableHead key={dimension.key}>{dimension.label}</TableHead>
              ))}
              <TableHead className="text-right">Forecast Hrs</TableHead>
              <TableHead className="text-right">Forecast Cost</TableHead>
              <TableHead className="text-right">Actual Hrs</TableHead>
              <TableHead className="text-right">Actual Cost</TableHead>
              <TableHead className="text-right">Variance Cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell className="text-muted-foreground" colSpan={report.dimensions.length + 5}>
                  No labor cost rows exist for this fiscal year yet.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => <LaborCostReportBodyRow key={reportRowKey(row)} row={row} />)
            )}
            <TableRow className="bg-secondary/60 hover:bg-secondary/60">
              <TableCell className="font-semibold text-primary" colSpan={report.dimensions.length}>
                Total
              </TableCell>
              <TableCell className="numeric-cell text-right font-semibold">{formatHours(report.totals.forecast_hours)}</TableCell>
              <TableCell className="numeric-cell text-right font-semibold text-primary">{formatCurrency(report.totals.forecast_cost)}</TableCell>
              <TableCell className="numeric-cell text-right font-semibold">{formatHours(report.totals.actual_hours)}</TableCell>
              <TableCell className="numeric-cell text-right font-semibold text-primary">{formatCurrency(report.totals.actual_cost)}</TableCell>
              <TableCell className="numeric-cell text-right font-semibold">{formatCurrency(report.totals.variance_cost)}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function LaborCostReportBodyRow({ row }: { row: LaborCostReportRow }) {
  return (
    <TableRow>
      {row.dimension_values.map((value) => (
        <TableCell key={`${value.key}:${value.label}`} className="font-medium">
          {value.href ? (
            <Link className="text-primary hover:underline" to={value.href}>
              {value.label}
            </Link>
          ) : (
            value.label
          )}
        </TableCell>
      ))}
      <TableCell className="numeric-cell text-right">{formatHours(row.forecast_hours)}</TableCell>
      <TableCell className="numeric-cell text-right font-medium text-primary">{formatCurrency(row.forecast_cost)}</TableCell>
      <TableCell className="numeric-cell text-right">{formatHours(row.actual_hours)}</TableCell>
      <TableCell className="numeric-cell text-right font-medium text-primary">{formatCurrency(row.actual_cost)}</TableCell>
      <TableCell className="numeric-cell text-right">{formatCurrency(row.variance_cost)}</TableCell>
    </TableRow>
  );
}

function DimensionSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ key: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-1">
      <span className="block text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <select className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm font-medium text-foreground" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.key} value={option.key}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function ReportMetric({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "warn" }) {
  return (
    <div className="rounded-md bg-secondary/70 px-4 py-3">
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <div className={cn("numeric-cell mt-1 text-xl font-semibold text-primary", tone === "warn" && "text-warning")}>{value}</div>
    </div>
  );
}

function reportRowKey(row: LaborCostReportRow) {
  return row.dimension_values.map((value) => `${value.key}:${value.label}`).join("|");
}

function activeDimensionOptions(
  leadDimension: LaborCostReportDimension,
  secondDimension: LaborCostReportOptionalDimension,
  thirdDimension: LaborCostReportOptionalDimension,
) {
  const selectedDimensions = [leadDimension, secondDimension, thirdDimension];
  const seen = new Set<string>();
  return selectedDimensions
    .filter((dimension): dimension is LaborCostReportDimension => dimension !== "none")
    .filter((dimension) => {
      if (seen.has(dimension)) return false;
      seen.add(dimension);
      return true;
    })
    .map((dimension) => DIMENSION_OPTIONS.find((option) => option.key === dimension) ?? { key: dimension, label: dimension });
}
