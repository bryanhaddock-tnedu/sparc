import { DatabaseZap, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import type { JiraIntegrationStatus, JiraProductMapping, JiraProjectCatalog, JiraUserMapping, Product, RoadmapItem, SyncRun, TeamMember } from "../types/api";

export function IntegrationsPage({ embedded = false }: { embedded?: boolean } = {}) {
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [userMappings, setUserMappings] = useState<JiraUserMapping[]>([]);
  const [productMappings, setProductMappings] = useState<JiraProductMapping[]>([]);
  const [jiraCatalog, setJiraCatalog] = useState<JiraProjectCatalog[]>([]);
  const [roadmapItems, setRoadmapItems] = useState<RoadmapItem[]>([]);
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [jiraStatus, setJiraStatus] = useState<JiraIntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [liveSyncing, setLiveSyncing] = useState(false);
  const [roadmapSyncing, setRoadmapSyncing] = useState(false);
  const [catalogRefreshing, setCatalogRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function loadData() {
    const [members, productRows, users, jiraProducts, catalogRows, roadmapRows, runs, status] = await Promise.all([
      api.teamMembers(),
      api.products(),
      api.userMappings(),
      api.productMappings(),
      api.jiraProjectCatalog(),
      api.roadmapItems(),
      api.syncRuns(),
      api.jiraIntegrationStatus(),
    ]);
    setTeamMembers(members);
    setProducts(productRows);
    setUserMappings(users);
    setProductMappings(jiraProducts);
    setJiraCatalog(catalogRows);
    setRoadmapItems(roadmapRows);
    setSyncRuns(runs);
    setJiraStatus(status);
  }

  useEffect(() => {
    loadData()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load integration data"))
      .finally(() => setLoading(false));
  }, []);

  async function runLiveSync() {
    setLiveSyncing(true);
    setError(null);
    setNotice(null);
    try {
      await api.syncLiveJiraRovo(fiscalYear);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run live Jira sync");
    } finally {
      setLiveSyncing(false);
    }
  }

  async function refreshCatalog() {
    setCatalogRefreshing(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.refreshJiraProjectCatalog();
      setJiraCatalog(result.projects);
      setNotice(`Jira project list refreshed: ${result.imported} projects available.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to refresh Jira project list");
    } finally {
      setCatalogRefreshing(false);
    }
  }

  async function runRoadmapSync() {
    setRoadmapSyncing(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.syncRoadmap();
      await loadData();
      setNotice(`Roadmap synced: ${result.roadmap_items} items and ${result.linked_issues} linked delivery tickets.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sync Jira roadmap");
    } finally {
      setRoadmapSyncing(false);
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

  const catalogLastCheckedAt = useMemo(() => latestCatalogCheckedAt(jiraCatalog), [jiraCatalog]);

  if (loading) return <LoadingBlock />;
  if (error && !jiraStatus) return <ErrorBlock message={error} />;

  const unmappedUserCount = userMappings.filter((mapping) => mapping.team_member_id === null).length;
  const unmappedProductCount = productMappings.filter((mapping) => mapping.product_id === null).length;

  return (
    <div className="space-y-5">
      <section className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end">
        <div>
          {embedded ? <h2 className="text-xl font-semibold">Jira Sync</h2> : <h1 className="text-2xl font-semibold">Jira Sync</h1>}
          <p className="mt-1 text-sm text-muted-foreground">
            Live Jira actual-hours sync, mappings, and sync history for {fiscalYearLabel} ({fiscalYearRangeLabel}).
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:items-end">
          {embedded ? null : <PageNav current="admin" />}
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button onClick={runRoadmapSync} disabled={roadmapSyncing || !jiraStatus?.configured} variant="outline">
              <RefreshCw className={`h-4 w-4 ${roadmapSyncing ? "animate-spin" : ""}`} />
              {roadmapSyncing ? "Syncing Roadmap" : "Sync Roadmap"}
            </Button>
            <Button onClick={runLiveSync} disabled={liveSyncing || !jiraStatus?.configured}>
              <DatabaseZap className={`h-4 w-4 ${liveSyncing ? "animate-pulse" : ""}`} />
              {liveSyncing ? "Syncing Jira" : "Sync Jira Actuals"}
            </Button>
          </div>
        </div>
      </section>

      {notice ? <div className="rounded-md border border-[color:var(--spark-cyan)] bg-accent/10 px-3 py-2 text-sm text-primary">{notice}</div> : null}
      {error ? <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <StatusCard label="Jira config" value={jiraStatus?.configured ? "Ready" : "Missing"} tone={jiraStatus?.configured ? "good" : "warn"} />
        <ProjectListStatusCard
          count={jiraCatalog.length}
          disabled={!jiraStatus?.configured}
          lastCheckedAt={catalogLastCheckedAt}
          refreshing={catalogRefreshing}
          onRefresh={refreshCatalog}
        />
        <StatusCard label="User mappings" value={`${userMappings.length - unmappedUserCount}/${userMappings.length}`} />
        <StatusCard label="Product mappings" value={`${productMappings.length - unmappedProductCount}/${productMappings.length}`} />
        <StatusCard label="Roadmap Items" value={`${roadmapItems.length}`} />
        <StatusCard label="Latest sync" value={syncRuns[0]?.status ?? "No runs"} />
      </section>

      {!jiraStatus?.configured ? (
        <div className="rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm">
          <div className="font-medium text-foreground">Live Jira sync is waiting on server configuration.</div>
          <div className="mt-1 text-muted-foreground">
            Missing: {jiraStatus?.missing.join(", ") || "Jira environment variables"}. These stay server-side and should come from local env or Key Vault.
          </div>
        </div>
      ) : null}

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

function ProjectListStatusCard({
  count,
  disabled,
  lastCheckedAt,
  refreshing,
  onRefresh,
}: {
  count: number;
  disabled: boolean;
  lastCheckedAt: string | null;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  return (
    <Card className="min-h-[118px]">
      <CardHeader className="flex flex-row items-start justify-between gap-2 p-4 pb-0">
        <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">Project list</CardTitle>
        <Button
          aria-label="Refresh Jira project list"
          className="h-7 w-7"
          disabled={disabled || refreshing}
          size="icon"
          title="Refresh Jira project list"
          variant="ghost"
          onClick={onRefresh}
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
        </Button>
      </CardHeader>
      <CardContent className="flex min-h-[72px] flex-col items-center justify-center p-4 pt-2">
        <div className="numeric-cell text-center text-2xl font-semibold leading-none text-foreground sm:text-3xl">{count}</div>
        <div className="mt-2 text-center text-xs leading-tight text-muted-foreground">
          {lastCheckedAt ? `Last refreshed ${formatDateTime(lastCheckedAt)}` : "Not refreshed yet"}
        </div>
      </CardContent>
    </Card>
  );
}

function StatusCard({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "good" | "warn" }) {
  const valueClass = tone === "good" ? "text-primary" : tone === "warn" ? "text-warning" : "text-foreground";
  return (
    <Card className="min-h-[118px]">
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-[72px] items-center justify-center p-4 pt-2">
        <div className={`numeric-cell text-center text-2xl font-semibold leading-none sm:text-3xl ${valueClass}`}>{value}</div>
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

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function latestCatalogCheckedAt(projects: JiraProjectCatalog[]) {
  const timestamps = projects.map((project) => Date.parse(project.last_checked_at)).filter(Number.isFinite);
  if (!timestamps.length) return null;
  return new Date(Math.max(...timestamps)).toISOString();
}
