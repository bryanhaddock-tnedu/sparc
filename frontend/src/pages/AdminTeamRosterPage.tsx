import { Upload, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import type { TeamImportResult, TeamMember } from "../types/api";

export function AdminTeamRosterPage({ embedded = false }: { embedded?: boolean } = {}) {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [importResult, setImportResult] = useState<TeamImportResult | null>(null);
  const [importing, setImporting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadMembers() {
    setMembers(await api.teamMembers());
  }

  useEffect(() => {
    loadMembers()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load team roster"))
      .finally(() => setLoading(false));
  }, []);

  async function importRoster(file: File | null) {
    if (!file) return;
    setImporting(true);
    setError(null);
    try {
      const result = await api.importTeamMembers(file);
      setImportResult(result);
      await loadMembers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to import team roster");
    } finally {
      setImporting(false);
    }
  }

  if (loading) return <LoadingBlock />;
  if (error && members.length === 0) return <ErrorBlock message={error} />;

  return (
    <div className="space-y-5">
      <section className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end">
        <div>
          {embedded ? <h2 className="text-xl font-semibold">Team Roster</h2> : <h1 className="text-2xl font-semibold">Team Roster</h1>}
          <p className="mt-1 text-sm text-muted-foreground">{members.length} rostered team members</p>
        </div>
        <div className="flex flex-col gap-2 sm:items-end">
          {embedded ? null : <PageNav current="admin" />}
          <Button asChild variant="outline">
            <Link to="/team">
              <Users className="h-4 w-4" />
              View Team
            </Link>
          </Button>
        </div>
      </section>

      {error ? <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}

      <section className="rounded-lg border bg-card p-4">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h3 className="text-sm font-semibold uppercase text-muted-foreground">Roster Import</h3>
            <p className="mt-1 text-sm text-muted-foreground">Upload CSV or XLSX roster data with the expected team member columns.</p>
          </div>
          <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            <Upload className="h-4 w-4" />
            {importing ? "Importing" : "Import Roster"}
            <input
              className="hidden"
              type="file"
              accept=".csv,.xlsx"
              disabled={importing}
              onChange={(event) => {
                void importRoster(event.target.files?.[0] ?? null);
                event.currentTarget.value = "";
              }}
            />
          </label>
        </div>
        {importResult ? (
          <div className="mt-4 grid gap-3 text-sm sm:grid-cols-4">
            <ImportMetric label="Created" value={importResult.created} />
            <ImportMetric label="Updated" value={importResult.updated} />
            <ImportMetric label="Skipped" value={importResult.skipped} />
            <ImportMetric label="Failed" value={importResult.failed} />
            {importResult.errors.length ? (
              <div className="sm:col-span-4">
                <div className="font-medium text-destructive">Import errors</div>
                <ul className="mt-1 space-y-1 text-destructive">
                  {importResult.errors.slice(0, 5).map((item) => (
                    <li key={`${item.row}-${item.message}`}>Row {item.row}: {item.message}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function ImportMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-h-[110px] rounded-md border bg-background p-3">
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <div className="flex min-h-[68px] items-center justify-center">
        <div className="numeric-cell text-center text-2xl font-semibold leading-none sm:text-3xl">{value}</div>
      </div>
    </div>
  );
}
