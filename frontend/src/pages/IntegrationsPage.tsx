import { ArrowLeft, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import type { JiraProductMapping, JiraUserMapping, Product, SyncRun, TeamMember } from "../types/api";

export function IntegrationsPage() {
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [userMappings, setUserMappings] = useState<JiraUserMapping[]>([]);
  const [productMappings, setProductMappings] = useState<JiraProductMapping[]>([]);
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    const [members, productRows, users, jiraProducts, runs] = await Promise.all([
      api.teamMembers(),
      api.products(),
      api.userMappings(),
      api.productMappings(),
      api.syncRuns(),
    ]);
    setTeamMembers(members);
    setProducts(productRows);
    setUserMappings(users);
    setProductMappings(jiraProducts);
    setSyncRuns(runs);
  }

  useEffect(() => {
    loadData()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load integration data"))
      .finally(() => setLoading(false));
  }, []);

  async function runSync() {
    setSyncing(true);
    setError(null);
    try {
      await api.syncMockJiraRovo();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run mock sync");
    } finally {
      setSyncing(false);
    }
  }

  async function updateUserMapping(mappingId: number, teamMemberId: number | null) {
    await api.updateUserMapping(mappingId, teamMemberId);
    await loadData();
  }

  async function updateProductMapping(mappingId: number, productId: number | null) {
    await api.updateProductMapping(mappingId, productId);
    await loadData();
  }

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;

  const unmappedUserCount = userMappings.filter((mapping) => mapping.team_member_id === null).length;
  const unmappedProductCount = productMappings.filter((mapping) => mapping.product_id === null).length;

  return (
    <div className="space-y-5">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/">
          <ArrowLeft className="h-4 w-4" />
          Dashboard
        </Link>
      </Button>

      <section className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold">Jira/Rovo Integration</h1>
          <p className="mt-1 text-sm text-muted-foreground">Mock actual-hours sync, mappings, and sync history.</p>
        </div>
        <Button onClick={runSync} disabled={syncing}>
          <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
          Mock Sync
        </Button>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        <StatusCard label="User mappings" value={`${userMappings.length - unmappedUserCount}/${userMappings.length}`} />
        <StatusCard label="Product mappings" value={`${productMappings.length - unmappedProductCount}/${productMappings.length}`} />
        <StatusCard label="Latest sync" value={syncRuns[0]?.status ?? "No runs"} />
      </section>

      <MappingTable title="Jira Users" unmapped={unmappedUserCount}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Jira User</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Team Member</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {userMappings.map((mapping) => (
              <TableRow key={mapping.id}>
                <TableCell>{mapping.jira_display_name}</TableCell>
                <TableCell>{mapping.jira_email ?? ""}</TableCell>
                <TableCell>
                  <select
                    className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={mapping.team_member_id ?? ""}
                    onChange={(event) => void updateUserMapping(mapping.id, event.target.value ? Number(event.target.value) : null)}
                  >
                    <option value="">Unmapped / external</option>
                    {teamMembers.map((member) => (
                      <option key={member.id} value={member.id}>
                        {member.name}
                      </option>
                    ))}
                  </select>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </MappingTable>

      <MappingTable title="Jira Products" unmapped={unmappedProductCount}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Jira Project</TableHead>
              <TableHead>Key</TableHead>
              <TableHead>Product</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {productMappings.map((mapping) => (
              <TableRow key={mapping.id}>
                <TableCell>{mapping.jira_project_name}</TableCell>
                <TableCell>{mapping.jira_project_key}</TableCell>
                <TableCell>
                  <select
                    className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={mapping.product_id ?? ""}
                    onChange={(event) => void updateProductMapping(mapping.id, event.target.value ? Number(event.target.value) : null)}
                  >
                    <option value="">Unmapped</option>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name}
                      </option>
                    ))}
                  </select>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </MappingTable>

      <Card>
        <CardHeader>
          <CardTitle>Sync History</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Status</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Imported</TableHead>
                <TableHead>Skipped</TableHead>
                <TableHead>Completed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {syncRuns.map((run) => (
                <TableRow key={run.id}>
                  <TableCell>
                    <Badge className={run.status === "completed" ? "border-primary/40 text-primary" : "border-destructive/40 text-destructive"}>
                      {run.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{run.source}</TableCell>
                  <TableCell className="numeric-cell">{run.imported_count}</TableCell>
                  <TableCell className="numeric-cell">{run.skipped_count}</TableCell>
                  <TableCell>{run.completed_at ? formatDate(run.completed_at) : ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function StatusCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="min-h-[118px]">
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-[72px] items-center justify-center p-4 pt-2">
        <div className="numeric-cell text-center text-2xl font-semibold leading-none sm:text-3xl">{value}</div>
      </CardContent>
    </Card>
  );
}

function MappingTable({ title, unmapped, children }: { title: string; unmapped: number; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{title}</h2>
        <Badge className={unmapped ? "border-destructive/40 text-destructive" : "border-primary/40 text-primary"}>
          {unmapped} unmapped
        </Badge>
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="overflow-x-auto">{children}</div>
      </div>
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}
