import { Download, FileSpreadsheet, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import type { AdminDataExportOption, AdminDataImportResult } from "../types/api";

const EXCLUDED_REFRESH_DATA = ["Actual Jira worklogs", "Sync history", "Jira project catalog snapshots", "Generated estimates"];

export function AdminDataPage() {
  const [options, setOptions] = useState<AdminDataExportOption[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<AdminDataImportResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api
      .adminDataExportOptions()
      .then((rows) => {
        setOptions(rows);
        setSelected(new Set(rows.filter((row) => row.default_selected).map((row) => row.key)));
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load admin data options"))
      .finally(() => setLoading(false));
  }, []);

  const selectedKeys = useMemo(() => options.filter((option) => selected.has(option.key)).map((option) => option.key), [options, selected]);

  function toggleOption(key: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  async function exportData() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const { blob, filename } = await api.exportAdminData(selectedKeys);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      window.URL.revokeObjectURL(url);
      setMessage(`Exported ${selectedKeys.length} data sets.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to export admin data");
    } finally {
      setBusy(false);
    }
  }

  async function importData() {
    if (!selectedFile) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    setImportResult(null);
    try {
      const result = await api.importAdminData(selectedFile, selectedKeys);
      setImportResult(result);
      setMessage("Import completed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to import admin data");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock />;
  if (error && options.length === 0) return <ErrorBlock message={error} />;

  return (
    <div className="space-y-5">
      <section className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold">Admin Data</h1>
          <p className="mt-1 text-sm text-muted-foreground">Move SPARC-owned setup, mapping, and forecast data between environments.</p>
        </div>
        <PageNav current="admin-data" />
      </section>

      {error ? <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
      {message ? <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-sm text-primary">{message}</div> : null}

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5" />
              Data Package Checklist
            </CardTitle>
            <p className="text-sm text-muted-foreground">Checked items are included in exports and processed during imports.</p>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              {options.map((option) => (
                <label key={option.key} className="flex min-h-[92px] gap-3 rounded-lg border bg-card p-3">
                  <input
                    className="mt-1 h-4 w-4"
                    type="checkbox"
                    checked={selected.has(option.key)}
                    onChange={() => toggleOption(option.key)}
                  />
                  <span>
                    <span className="block text-sm font-semibold">{option.label}</span>
                    <span className="mt-1 block text-sm text-muted-foreground">{option.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Export</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">Creates an import-ready zip package with one CSV per selected data set.</p>
              <Button className="w-full" onClick={() => void exportData()} disabled={busy || selectedKeys.length === 0}>
                <Download className="h-4 w-4" />
                Export Selected Data
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Import</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                type="file"
                accept=".zip,.xlsx,.json"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
              <Button className="w-full" variant="outline" onClick={() => void importData()} disabled={busy || selectedKeys.length === 0 || !selectedFile}>
                <Upload className="h-4 w-4" />
                Import Selected Data
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="rounded-lg border bg-muted/20 p-4">
        <div className="mb-3 text-sm font-semibold uppercase text-muted-foreground">Always excluded from this package</div>
        <div className="flex flex-wrap gap-2">
          {EXCLUDED_REFRESH_DATA.map((item) => (
            <Badge key={item}>{item}</Badge>
          ))}
        </div>
      </section>

      {importResult ? <ImportSummary result={importResult} /> : null}
    </div>
  );
}

function ImportSummary({ result }: { result: AdminDataImportResult }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Import Summary</h2>
      <div className="overflow-hidden rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Data Set</TableHead>
              <TableHead className="numeric-cell">Created</TableHead>
              <TableHead className="numeric-cell">Updated</TableHead>
              <TableHead className="numeric-cell">Skipped</TableHead>
              <TableHead className="numeric-cell">Failed</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.datasets.map((row) => (
              <TableRow key={row.key}>
                <TableCell className="font-medium">{row.label}</TableCell>
                <TableCell className="numeric-cell">{row.created}</TableCell>
                <TableCell className="numeric-cell">{row.updated}</TableCell>
                <TableCell className="numeric-cell">{row.skipped}</TableCell>
                <TableCell className="numeric-cell">{row.failed}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {result.errors.length ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm">
          <div className="font-semibold text-destructive">Rows needing attention</div>
          <ul className="mt-2 space-y-1 text-destructive">
            {result.errors.slice(0, 8).map((error) => (
              <li key={`${error.sheet}-${error.row}-${error.message}`}>
                {error.sheet} row {error.row}: {error.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
