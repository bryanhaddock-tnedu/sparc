import { ArrowLeft, Upload } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";

import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { formatBillRate } from "../lib/teamMembers";
import type { TeamImportResult, TeamMember } from "../types/api";

export function TeamManagementPage() {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [importResult, setImportResult] = useState<TeamImportResult | null>(null);
  const [importing, setImporting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMembers = useCallback(async () => {
    setMembers(await api.teamMembers());
  }, []);

  useEffect(() => {
    loadMembers()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load team"))
      .finally(() => setLoading(false));
  }, [loadMembers]);

  const updateBillRate = useCallback(async (member: TeamMember, billRate: number) => {
    const updated = await api.updateTeamMember(member.id, { bill_rate: billRate });
    setMembers((current) => current.map((row) => (row.id === member.id ? updated : row)));
  }, []);

  const columns = useMemo<ColumnDef<TeamMember>[]>(
    () => [
      {
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => (
          <Link className="font-medium text-primary hover:underline" to={`/team-members/${row.original.id}`}>
            {row.original.name}
          </Link>
        ),
      },
      { accessorKey: "role", header: "Role" },
      { accessorKey: "team", header: "Team" },
      {
        accessorKey: "bill_rate",
        header: "Bill Rate",
        cell: ({ row }) => <BillRateInput member={row.original} onSave={updateBillRate} />,
      },
      { accessorKey: "employment_type", header: "Employment Type" },
      {
        accessorKey: "contracting_company",
        header: "Contracting Company",
        cell: ({ row }) => row.original.contracting_company ?? "",
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => (
          <Badge className={row.original.status === "active" ? "border-primary/40 text-primary" : "border-muted text-muted-foreground"}>
            {row.original.status}
          </Badge>
        ),
      },
      {
        accessorKey: "updated_at",
        header: "Last Updated",
        cell: ({ row }) => formatDate(row.original.updated_at),
      },
    ],
    [updateBillRate],
  );

  const table = useReactTable({ data: members, columns, getCoreRowModel: getCoreRowModel() });

  async function importRoster(file: File | null) {
    if (!file) return;
    setImporting(true);
    setError(null);
    try {
      const result = await api.importTeamMembers(file);
      setImportResult(result);
      await loadMembers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to import team members");
    } finally {
      setImporting(false);
    }
  }

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;

  return (
    <div className="space-y-5">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/">
          <ArrowLeft className="h-4 w-4" />
          Dashboard
        </Link>
      </Button>

      <div>
        <h1 className="text-2xl font-semibold">Team Management</h1>
        <p className="mt-1 text-sm text-muted-foreground">{members.length} rostered team members</p>
      </div>

      <section className="rounded-lg border bg-card p-4">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-sm font-semibold uppercase text-muted-foreground">Roster Import</h2>
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

      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id}>
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
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

function BillRateInput({ member, onSave }: { member: TeamMember; onSave: (member: TeamMember, billRate: number) => Promise<void> }) {
  const [value, setValue] = useState(member.bill_rate > 0 ? String(member.bill_rate) : "");
  const [saving, setSaving] = useState(false);

  useEffect(() => setValue(member.bill_rate > 0 ? String(member.bill_rate) : ""), [member.bill_rate]);

  async function commit() {
    const nextValue = value.trim() === "" ? 0 : Number(value);
    if (!Number.isFinite(nextValue) || nextValue < 0 || nextValue === member.bill_rate) return;
    setSaving(true);
    try {
      await onSave(member, nextValue);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="w-28">
      <Input
        aria-label={`${member.name} bill rate`}
        className="numeric-cell h-8"
        disabled={saving}
        inputMode="decimal"
        pattern="[0-9]*"
        placeholder="Not set"
        type="text"
        value={value}
        onBlur={commit}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
        }}
      />
      <div className="numeric-cell mt-1 text-xs text-muted-foreground">{formatBillRate(member.bill_rate, member.employment_type)}</div>
    </div>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}
