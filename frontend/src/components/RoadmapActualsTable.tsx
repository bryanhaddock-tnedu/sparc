import { Link } from "react-router-dom";

import { productDetailPath, teamMemberDetailPath } from "../lib/routes";
import { formatCurrency, formatHours } from "../lib/utils";
import type { RoadmapActualRow } from "../types/api";
import { Badge } from "./ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

type RoadmapActualsTableProps = {
  rows: RoadmapActualRow[];
  showProduct?: boolean;
  showTeamMember?: boolean;
  title?: string;
};

export function RoadmapActualsTable({
  rows,
  showProduct = false,
  showTeamMember = false,
  title = "Roadmap Actuals",
}: RoadmapActualsTableProps) {
  const totals = rows.reduce(
    (acc, row) => {
      acc.hours += row.actual_hours;
      acc.cost += row.actual_cost;
      acc.worklogs += row.worklog_count;
      acc.tickets += row.ticket_count;
      return acc;
    },
    { hours: 0, cost: 0, worklogs: 0, tickets: 0 },
  );
  const mappedCount = rows.filter((row) => row.mapping_status === "mapped").length;
  const gapCount = rows.length - mappedCount;

  return (
    <section className="space-y-3">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">Actual Jira worklogs attributed to roadmap items for billing review.</p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <SummaryPill label="Hours" value={formatHours(totals.hours)} />
          <SummaryPill label="Cost" value={formatCurrency(totals.cost)} />
          <SummaryPill label="Tickets" value={String(totals.tickets)} />
          <SummaryPill label="Gaps" value={String(gapCount)} tone={gapCount ? "warn" : "default"} />
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Roadmap Item</TableHead>
                {showProduct ? <TableHead>Product</TableHead> : null}
                {showTeamMember ? <TableHead>Team Member</TableHead> : null}
                <TableHead>Bucket</TableHead>
                <TableHead>Tickets</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Hours</TableHead>
                <TableHead className="text-right">Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length ? (
                rows.map((row) => (
                  <TableRow key={rowKey(row)}>
                    <TableCell>
                      <RoadmapItemCell row={row} />
                    </TableCell>
                    {showProduct ? (
                      <TableCell>
                        <Link className="font-medium text-primary hover:underline" to={productDetailPath(row)}>
                          {row.product}
                        </Link>
                      </TableCell>
                    ) : null}
                    {showTeamMember ? (
                      <TableCell>
                        <Link className="font-medium text-primary hover:underline" to={teamMemberDetailPath(row)}>
                          {row.team_member}
                        </Link>
                      </TableCell>
                    ) : null}
                    <TableCell>{row.bucket}</TableCell>
                    <TableCell>
                      <div className="max-w-72 truncate text-sm" title={row.ticket_keys.join(", ")}>
                        {row.ticket_keys.length ? row.ticket_keys.join(", ") : "-"}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {row.worklog_count} {row.worklog_count === 1 ? "worklog" : "worklogs"}
                      </div>
                    </TableCell>
                    <TableCell>
                      <MappingBadge status={row.mapping_status} />
                    </TableCell>
                    <TableCell className="numeric-cell text-right font-semibold">{formatHours(row.actual_hours)}</TableCell>
                    <TableCell className="numeric-cell text-right font-semibold text-primary">{formatCurrency(row.actual_cost)}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell className="py-6 text-sm text-muted-foreground" colSpan={6 + Number(showProduct) + Number(showTeamMember)}>
                    No roadmap-attributed actuals exist for this fiscal year yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </section>
  );
}

function RoadmapItemCell({ row }: { row: RoadmapActualRow }) {
  if (row.mapping_status === "ambiguous") {
    return (
      <div>
        <div className="font-medium text-warning">Ambiguous roadmap mapping</div>
        <div className="text-xs text-muted-foreground">Ticket is linked to multiple Roadmap Items.</div>
      </div>
    );
  }
  if (row.mapping_status === "unmapped") {
    return (
      <div>
        <div className="font-medium text-muted-foreground">Unmapped Roadmap Item</div>
        <div className="text-xs text-muted-foreground">No Roadmap Item link found for these tickets.</div>
      </div>
    );
  }
  return (
    <div>
      <div className="font-medium text-primary">{row.roadmap_item_key}</div>
      <div className="max-w-96 truncate text-sm text-foreground" title={row.roadmap_item_title ?? ""}>
        {row.roadmap_item_title}
      </div>
      <div className="text-xs text-muted-foreground">{row.roadmap_item_status ?? "No status"}</div>
    </div>
  );
}

function MappingBadge({ status }: { status: string }) {
  if (status === "mapped") return <Badge className="border-primary/40 text-primary">mapped</Badge>;
  if (status === "ambiguous") return <Badge className="border-warning/50 text-warning">ambiguous</Badge>;
  return <Badge className="border-muted text-muted-foreground">unmapped</Badge>;
}

function SummaryPill({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "warn" }) {
  return (
    <div className="rounded-md bg-secondary px-3 py-2">
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <div className={`numeric-cell text-right text-base font-semibold ${tone === "warn" ? "text-warning" : "text-primary"}`}>{value}</div>
    </div>
  );
}

function rowKey(row: RoadmapActualRow) {
  return [row.mapping_status, row.roadmap_item_id ?? "none", row.product_id, row.team_member_id, row.bucket_id, row.ticket_keys.join("|")].join(":");
}
