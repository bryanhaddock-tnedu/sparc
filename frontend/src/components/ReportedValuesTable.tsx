import { ChevronDown, ChevronRight } from "lucide-react";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import { productDetailPath } from "../lib/routes";
import { formatHours } from "../lib/utils";
import type { ReportedValueRow } from "../types/api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { TeamMemberNameLink } from "./TeamMemberNameLink";

export function ReportedValuesTable({
  rows,
  title = "Reported Hours Audit",
  showProduct = false,
  showTeamMember = false,
  defaultExpanded = false,
}: {
  rows: ReportedValueRow[];
  title?: string;
  showProduct?: boolean;
  showTeamMember?: boolean;
  defaultExpanded?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const tableId = useId();
  const totals = rows.reduce(
    (acc, row) => {
      acc.forecast += row.forecast_hours;
      acc.actual += row.actual_hours;
      acc.estimated += row.estimated_hours;
      acc.reported += row.reported_hours;
      return acc;
    },
    { forecast: 0, actual: 0, estimated: 0, reported: 0 },
  );

  return (
    <section className="space-y-3">
      <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground">Forecast, actual, estimated, and reported hours stay separate for auditability.</p>
        </div>
        <div className="flex flex-col gap-2 sm:items-end">
          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            <TotalPill label="Forecast" value={totals.forecast} />
            <TotalPill label="Actual" value={totals.actual} />
            <TotalPill label="Estimated" value={totals.estimated} />
            <TotalPill label="Reported" value={totals.reported} />
          </div>
          <Button
            aria-controls={tableId}
            aria-expanded={isExpanded}
            className="w-full sm:w-auto"
            onClick={() => setIsExpanded((current) => !current)}
            size="sm"
            type="button"
            variant="outline"
          >
            {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            {isExpanded ? "Hide rows" : `Show ${rows.length} ${rows.length === 1 ? "row" : "rows"}`}
          </Button>
        </div>
      </div>
      {isExpanded ? (
        <div className="overflow-hidden rounded-lg border bg-card" id={tableId}>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  {showProduct ? <TableHead>Product</TableHead> : null}
                  {showTeamMember ? <TableHead>Team Member</TableHead> : null}
                  <TableHead>Bucket</TableHead>
                  <TableHead>Month</TableHead>
                  <TableHead>Forecast</TableHead>
                  <TableHead>Actual</TableHead>
                  <TableHead>Estimated</TableHead>
                  <TableHead>Reported</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.length ? (
                  rows.map((row) => (
                    <TableRow key={`${row.product_id}-${row.team_member_id}-${row.bucket_id}-${row.fiscal_month_id}`}>
                      {showProduct ? (
                        <TableCell>
                          <Link className="font-medium text-primary hover:underline" to={productDetailPath(row)}>
                            {row.product}
                          </Link>
                        </TableCell>
                      ) : null}
                      {showTeamMember ? (
                        <TableCell>
                          <TeamMemberNameLink className="font-medium" linkClassName="text-primary hover:underline" member={row}>
                            {row.team_member}
                          </TeamMemberNameLink>
                        </TableCell>
                      ) : null}
                      <TableCell>{row.bucket}</TableCell>
                      <TableCell>{row.month_label}</TableCell>
                      <TableCell className="numeric-cell">{formatHours(row.forecast_hours)}</TableCell>
                      <TableCell className="numeric-cell">{formatHours(row.actual_hours)}</TableCell>
                      <TableCell className="numeric-cell">{formatHours(row.estimated_hours)}</TableCell>
                      <TableCell className="numeric-cell font-semibold text-primary">{formatHours(row.reported_hours)}</TableCell>
                      <TableCell>
                        <SourceBadge source={row.reported_source} />
                      </TableCell>
                      <TableCell className="min-w-56 text-muted-foreground">{row.reported_reason}</TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell className="py-5 text-muted-foreground" colSpan={8 + Number(showProduct) + Number(showTeamMember)}>
                      No forecast, actual, or estimated values exist for this view yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function TotalPill({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-secondary px-3 py-2">
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <div className="numeric-cell text-right text-lg font-semibold text-primary">{formatHours(value)}</div>
    </div>
  );
}

function SourceBadge({ source }: { source: string }) {
  const className =
    source === "actual"
      ? "border-primary/40 text-primary"
      : source === "estimated"
        ? "border-spark-orange/50 text-spark-orange"
        : source === "forecast"
        ? "border-spark-cyan/50 text-spark-cyan"
          : "border-muted text-muted-foreground";
  return <Badge className={className}>{source}</Badge>;
}
