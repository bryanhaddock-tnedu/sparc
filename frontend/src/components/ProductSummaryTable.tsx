import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronsUpDown, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { ProductSummaryRow } from "../types/api";
import { productDetailPath } from "../lib/routes";
import { cn, formatCurrency, formatHours } from "../lib/utils";
import { Button } from "./ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

type ProductSortId =
  | "product"
  | "team_members"
  | "budget_amount"
  | "budget_utilization_percent"
  | "forecasted_hours"
  | "forecasted_cost"
  | "fytd_hours"
  | "fytd_cost";

const sortOptions: Array<{ id: ProductSortId; label: string; defaultDesc: boolean }> = [
  { id: "fytd_cost", label: "Actual $", defaultDesc: true },
  { id: "fytd_hours", label: "Actual Hrs", defaultDesc: true },
  { id: "forecasted_cost", label: "Forecast $", defaultDesc: true },
  { id: "forecasted_hours", label: "Forecast Hrs", defaultDesc: true },
  { id: "budget_utilization_percent", label: "Budget Used", defaultDesc: true },
  { id: "budget_amount", label: "Budget", defaultDesc: true },
  { id: "team_members", label: "Team Members", defaultDesc: true },
  { id: "product", label: "Product", defaultDesc: false },
];

const defaultSorting: SortingState = [
  { id: "fytd_cost", desc: true },
  { id: "forecasted_cost", desc: true },
];

const numericColumns = new Set<ProductSortId>([
  "team_members",
  "budget_amount",
  "budget_utilization_percent",
  "forecasted_hours",
  "forecasted_cost",
  "fytd_hours",
  "fytd_cost",
]);

const hourColumnIds = new Set<ProductSortId>(["forecasted_hours", "fytd_hours"]);

type ProductSummaryColumn = ColumnDef<ProductSummaryRow> & { accessorKey: ProductSortId };

const columns: ProductSummaryColumn[] = [
  {
    accessorKey: "product",
    header: "Product",
    sortDescFirst: false,
    cell: ({ row }) => (
      <Link className="font-medium text-primary hover:underline" to={productDetailPath(row.original)}>
        {row.original.product}
      </Link>
    ),
  },
  {
    accessorKey: "team_members",
    header: "Team Members",
    sortDescFirst: true,
    cell: ({ row }) => <span className="numeric-cell">{row.original.team_members}</span>,
  },
  {
    accessorKey: "budget_amount",
    header: "Budget",
    sortDescFirst: true,
    cell: ({ row }) => <span className="numeric-cell">{formatCurrency(row.original.budget_amount)}</span>,
  },
  {
    accessorKey: "budget_utilization_percent",
    header: "Budget Used",
    sortDescFirst: true,
    cell: ({ row }) => <span className="numeric-cell">{row.original.budget_utilization_percent.toFixed(1)}%</span>,
  },
  {
    accessorKey: "forecasted_hours",
    header: "Forecast Hrs",
    sortDescFirst: true,
    cell: ({ row }) => <span className="numeric-cell">{formatHours(row.original.forecasted_hours)}</span>,
  },
  {
    accessorKey: "forecasted_cost",
    header: "Forecast $",
    sortDescFirst: true,
    cell: ({ row }) => <span className="numeric-cell">{formatCurrency(row.original.forecasted_cost)}</span>,
  },
  {
    accessorKey: "fytd_hours",
    header: "Actual Hrs",
    sortDescFirst: true,
    cell: ({ row }) => <span className="numeric-cell">{formatHours(row.original.fytd_hours)}</span>,
  },
  {
    accessorKey: "fytd_cost",
    header: "Actual $",
    sortDescFirst: true,
    cell: ({ row }) => <span className="numeric-cell">{formatCurrency(row.original.fytd_cost)}</span>,
  },
];

export function ProductSummaryTable({ rows, canViewHours = true }: { rows: ProductSummaryRow[]; canViewHours?: boolean }) {
  const [sorting, setSorting] = useState<SortingState>(defaultSorting);
  const availableSortOptions = useMemo(() => sortOptions.filter((option) => canViewHours || !hourColumnIds.has(option.id)), [canViewHours]);
  const visibleColumns = useMemo(() => columns.filter((column) => canViewHours || !hourColumnIds.has(column.accessorKey)), [canViewHours]);
  const activeSortSummary = useMemo(() => {
    return sorting
      .map((sort) => {
        const option = availableSortOptions.find((item) => item.id === sort.id);
        if (!option) return null;
        return `${option.label} ${sort.desc ? "descending" : "ascending"}`;
      })
      .filter(Boolean)
      .join(", then ");
  }, [availableSortOptions, sorting]);

  useEffect(() => {
    if (canViewHours) return;
    setSorting((current) => {
      const filtered = current.filter((sort) => !hourColumnIds.has(sort.id as ProductSortId));
      return filtered.length ? filtered : defaultSorting;
    });
  }, [canViewHours]);

  const table = useReactTable({
    data: rows,
    columns: visibleColumns,
    state: { sorting },
    onSortingChange: setSorting,
    enableMultiSort: true,
    enableSortingRemoval: false,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  function setSortColumn(index: number, nextId: ProductSortId | "") {
    const next = [...sorting];
    if (!nextId) {
      next.splice(index, 1);
      setSorting(next);
      return;
    }

    const option = availableSortOptions.find((item) => item.id === nextId);
    const duplicateIndex = next.findIndex((sort, sortIndex) => sort.id === nextId && sortIndex !== index);
    if (duplicateIndex >= 0) next.splice(duplicateIndex, 1);

    next[index] = { id: nextId, desc: option?.defaultDesc ?? true };
    setSorting(next.filter(Boolean));
  }

  function setSortDirection(index: number, desc: boolean) {
    const next = [...sorting];
    if (!next[index]) return;
    next[index] = { ...next[index], desc };
    setSorting(next);
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="flex flex-col gap-2 border-b bg-secondary/30 px-3 py-2 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase text-muted-foreground">Sort priority</div>
          <div className="sr-only" aria-live="polite">
            {activeSortSummary || "No active sort"}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SortSelect
            label="Primary"
            value={(sorting[0]?.id as ProductSortId | undefined) ?? ""}
            onChange={(value) => setSortColumn(0, value)}
            disabledIds={sorting[1]?.id ? [sorting[1].id as ProductSortId] : []}
            options={availableSortOptions}
          />
          <DirectionSelect
            label="Primary direction"
            value={sorting[0]?.desc ?? true}
            onChange={(desc) => setSortDirection(0, desc)}
            disabled={!sorting[0]}
          />
          <span className="text-xs font-semibold uppercase text-muted-foreground">Then</span>
          <SortSelect
            label="Secondary"
            value={(sorting[1]?.id as ProductSortId | undefined) ?? ""}
            onChange={(value) => setSortColumn(1, value)}
            allowNone
            disabledIds={sorting[0]?.id ? [sorting[0].id as ProductSortId] : []}
            options={availableSortOptions}
          />
          <DirectionSelect
            label="Secondary direction"
            value={sorting[1]?.desc ?? true}
            onChange={(desc) => setSortDirection(1, desc)}
            disabled={!sorting[1]}
          />
          <Button type="button" variant="outline" size="sm" className="h-8 px-2" onClick={() => setSorting(defaultSorting)}>
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Reset
          </Button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const sortDirection = header.column.getIsSorted();
                  const sortIndex = sorting.findIndex((sort) => sort.id === header.column.id);
                  const isNumeric = numericColumns.has(header.column.id as ProductSortId);

                  return (
                    <TableHead key={header.id} className={cn(isNumeric && "text-right")}>
                      {header.isPlaceholder ? null : (
                        <button
                          type="button"
                          className={cn(
                            "inline-flex w-full items-center gap-1.5 rounded-sm py-1 text-left transition-colors hover:text-foreground",
                            isNumeric && "justify-end text-right",
                          )}
                          onClick={header.column.getToggleSortingHandler()}
                          aria-label={`Sort by ${String(header.column.columnDef.header)}`}
                        >
                          <span>{flexRender(header.column.columnDef.header, header.getContext())}</span>
                          {sortDirection === "asc" ? (
                            <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                          ) : sortDirection === "desc" ? (
                            <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                          ) : (
                            <ChevronsUpDown className="h-3.5 w-3.5 opacity-55" aria-hidden="true" />
                          )}
                          {sortIndex >= 0 ? (
                            <span className="numeric-cell rounded-sm bg-primary px-1.5 py-0.5 text-[10px] leading-none text-primary-foreground">
                              {sortIndex + 1}
                            </span>
                          ) : null}
                        </button>
                      )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id} className={cn(numericColumns.has(cell.column.id as ProductSortId) && "text-right")}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function SortSelect({
  label,
  value,
  onChange,
  options,
  allowNone = false,
  disabledIds = [],
}: {
  label: string;
  value: ProductSortId | "";
  onChange: (value: ProductSortId | "") => void;
  options: Array<{ id: ProductSortId; label: string; defaultDesc: boolean }>;
  allowNone?: boolean;
  disabledIds?: ProductSortId[];
}) {
  return (
    <label className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
      {label}
      <select
        className="h-8 rounded-md border border-input bg-background px-2 text-sm font-medium normal-case text-foreground"
        value={value}
        onChange={(event) => onChange(event.target.value as ProductSortId | "")}
      >
        {allowNone ? <option value="">None</option> : null}
        {options.map((option) => (
          <option key={option.id} value={option.id} disabled={disabledIds.includes(option.id)}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function DirectionSelect({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: boolean;
  onChange: (desc: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <select
      aria-label={label}
      className="h-8 rounded-md border border-input bg-background px-2 text-sm font-medium disabled:opacity-50"
      value={value ? "desc" : "asc"}
      onChange={(event) => onChange(event.target.value === "desc")}
      disabled={disabled}
    >
      <option value="desc">High to low</option>
      <option value="asc">Low to high</option>
    </select>
  );
}
