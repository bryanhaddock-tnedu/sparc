import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { Link } from "react-router-dom";

import type { ProductSummaryRow } from "../types/api";
import { formatCurrency, formatHours } from "../lib/utils";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

const columns: ColumnDef<ProductSummaryRow>[] = [
  {
    accessorKey: "product",
    header: "Product",
    cell: ({ row }) => (
      <Link className="font-medium text-primary hover:underline" to={`/products/${row.original.product_id}`}>
        {row.original.product}
      </Link>
    ),
  },
  {
    accessorKey: "team_members",
    header: "# Team Members",
    cell: ({ row }) => <span className="numeric-cell">{row.original.team_members}</span>,
  },
  {
    accessorKey: "budget_amount",
    header: "Budget",
    cell: ({ row }) => <span className="numeric-cell">{formatCurrency(row.original.budget_amount)}</span>,
  },
  {
    accessorKey: "budget_utilization_percent",
    header: "Budget Used",
    cell: ({ row }) => <span className="numeric-cell">{row.original.budget_utilization_percent.toFixed(1)}%</span>,
  },
  {
    accessorKey: "forecasted_hours",
    header: "Forecasted Hours",
    cell: ({ row }) => <span className="numeric-cell">{formatHours(row.original.forecasted_hours)}</span>,
  },
  {
    accessorKey: "forecasted_cost",
    header: "Forecasted Cost",
    cell: ({ row }) => <span className="numeric-cell">{formatCurrency(row.original.forecasted_cost)}</span>,
  },
  {
    accessorKey: "fytd_hours",
    header: "FYTD Hours",
    cell: ({ row }) => <span className="numeric-cell">{formatHours(row.original.fytd_hours)}</span>,
  },
  {
    accessorKey: "fytd_cost",
    header: "FYTD Cost",
    cell: ({ row }) => <span className="numeric-cell">{formatCurrency(row.original.fytd_cost)}</span>,
  },
];

export function ProductSummaryTable({ rows }: { rows: ProductSummaryRow[] }) {
  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel() });

  return (
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
  );
}
