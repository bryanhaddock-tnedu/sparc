import { AlertTriangle, Eye, History, Play, RefreshCw, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { TeamMemberNameLink } from "../components/TeamMemberNameLink";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import { formatHours } from "../lib/utils";
import type { EstimatedIssueAllocation, EstimationPreview, EstimationProfile, EstimationRun, JiraTeamEstimationProfile } from "../types/api";

type ProfileForm = {
  name: string;
  description: string;
  monthlyCapacityHours: string;
  actualCompletenessThreshold: string;
  staleTicketWindowDays: string;
  forecastFutureMonths: boolean;
  futureMonthAverageWindow: string;
  excludedStatuses: string;
  lowActivityStatuses: string;
  excludedJiraProjectKeys: string;
  projectPauseDates: string;
  workTypeFieldPriority: string;
  storyPointWeightingEnabled: boolean;
  notes: string;
};

export function EstimationSettingsPage() {
  const { fiscalYear, fiscalYearLabel, fiscalYearRangeLabel } = useFiscalYear();
  const [profiles, setProfiles] = useState<EstimationProfile[]>([]);
  const [jiraTeamProfiles, setJiraTeamProfiles] = useState<JiraTeamEstimationProfile[]>([]);
  const [runs, setRuns] = useState<EstimationRun[]>([]);
  const [allocations, setAllocations] = useState<EstimatedIssueAllocation[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [form, setForm] = useState<ProfileForm | null>(null);
  const [preview, setPreview] = useState<EstimationPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? profiles[0] ?? null,
    [profiles, selectedProfileId],
  );

  async function loadData() {
    setError(null);
    const [profileResults, runResults, teamProfiles] = await Promise.all([api.estimationProfiles(), api.estimationRuns(fiscalYear), api.jiraTeamEstimationProfiles()]);
    const nextProfile = profileResults.find((profile) => profile.id === selectedProfileId) ?? profileResults[0] ?? null;
    setProfiles(profileResults);
    setJiraTeamProfiles(teamProfiles);
    setRuns(runResults);
    setSelectedProfileId(nextProfile?.id ?? null);
    setForm(nextProfile ? formFromProfile(nextProfile) : null);
    setAllocations(runResults[0] ? await api.estimationRunAllocations(runResults[0].id, 75) : []);
  }

  useEffect(() => {
    setLoading(true);
    loadData()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load estimation settings"))
      .finally(() => setLoading(false));
  }, [fiscalYear]);

  async function saveProfile() {
    if (!form || !selectedProfile) return;
    const payload = profilePayload(form);
    if (!payload) {
      setError("Capacity, threshold, stale window, and average window must be valid numbers.");
      return;
    }
    setWorking("save");
    setError(null);
    setMessage(null);
    try {
      await api.updateEstimationProfile(selectedProfile.id, payload);
      setMessage("Estimation profile saved.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save profile");
    } finally {
      setWorking(null);
    }
  }

  async function previewImpact() {
    if (!selectedProfile) return;
    setWorking("preview");
    setError(null);
    setMessage(null);
    try {
      const result = await api.previewEstimation({ fiscal_year: fiscalYear, profile_id: selectedProfile.id });
      setPreview(result);
      setMessage("Preview generated without creating an estimation run.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to preview estimation");
    } finally {
      setWorking(null);
    }
  }

  async function runEstimation() {
    if (!selectedProfile) return;
    setWorking("run");
    setError(null);
    setMessage(null);
    try {
      const result = await api.runEstimation({ fiscal_year: fiscalYear, profile_id: selectedProfile.id });
      setPreview(result);
      setMessage(`Estimation run #${result.run_id} completed.`);
      const nextRuns = await api.estimationRuns(fiscalYear);
      setRuns(nextRuns);
      setAllocations(result.run_id ? await api.estimationRunAllocations(result.run_id, 75) : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run estimation");
    } finally {
      setWorking(null);
    }
  }

  if (loading) return <LoadingBlock />;
  if (error && !form) return <ErrorBlock message={error} />;

  return (
    <div className="space-y-6">
      <section className="flex flex-col justify-between gap-4 border-b pb-5 lg:flex-row lg:items-end">
        <div>
          <h1 className="text-2xl font-semibold">Estimation Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Configure, preview, and run Jira activity-based estimated hours for {fiscalYearLabel} ({fiscalYearRangeLabel}).
          </p>
        </div>
        <div className="flex flex-col gap-2 lg:items-end">
          <PageNav />
          <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void loadData()} disabled={!!working}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" onClick={() => void previewImpact()} disabled={!selectedProfile || !!working}>
            <Eye className="h-4 w-4" />
            {working === "preview" ? "Previewing" : "Preview Impact"}
          </Button>
          <Button onClick={() => void runEstimation()} disabled={!selectedProfile || !!working}>
            <Play className="h-4 w-4" />
            {working === "run" ? "Running" : "Run Estimation"}
          </Button>
          </div>
        </div>
      </section>

      {error ? <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
      {message ? <div className="rounded-md border border-primary/30 bg-primary/5 p-3 text-sm text-primary">{message}</div> : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
        <Card>
          <CardHeader>
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <CardTitle>Active Profile</CardTitle>
              <div className="flex gap-2">
                <select
                  aria-label="Estimation profile"
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                  value={selectedProfileId ?? ""}
                  onChange={(event) => {
                    const profile = profiles.find((item) => item.id === Number(event.target.value)) ?? null;
                    setSelectedProfileId(profile?.id ?? null);
                    setForm(profile ? formFromProfile(profile) : null);
                  }}
                >
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
                <Button onClick={() => void saveProfile()} disabled={!form || !!working}>
                  <Save className="h-4 w-4" />
                  {working === "save" ? "Saving" : "Save"}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>{form ? <ProfileEditor form={form} onChange={setForm} disabled={!!working} /> : null}</CardContent>
        </Card>

        <div className="space-y-4">
          <PreviewCard preview={preview} />
          <Card>
            <CardHeader>
              <CardTitle>Policy Guardrails</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <Guardrail text="Actual, Estimated, Forecast, and Reported hours are stored and displayed separately." />
              <Guardrail text="Unknown Jira project keys become unmapped references for review." />
              <Guardrail text="Excluded statuses/projects generate audit rows with zero counted estimate." />
            </CardContent>
          </Card>
        </div>
      </section>

      <RunHistory runs={runs} />
      <AllocationAudit rows={allocations} />
      <JiraTeamProfilesPanel profiles={jiraTeamProfiles} onChanged={loadData} />
    </div>
  );
}

function JiraTeamProfilesPanel({ profiles, onChanged }: { profiles: JiraTeamEstimationProfile[]; onChanged: () => Promise<void> }) {
  const [form, setForm] = useState({ jira_team: "Product Maintenance", velocity_story_points: "75.8", developer_capacity_hours: "360", qa_percent: "20", po_percent: "15", notes: "" });
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save() {
    const values = [form.velocity_story_points, form.developer_capacity_hours, form.qa_percent, form.po_percent].map(Number);
    if (!form.jira_team.trim() || values.some((value) => !Number.isFinite(value) || value < 0) || values[0] === 0 || values[1] === 0) { setError("Enter a Jira Team, velocity, capacity, and non-negative percentages."); return; }
    setWorking(true); setError(null);
    const payload = { jira_team: form.jira_team.trim(), velocity_story_points: values[0], developer_capacity_hours: values[1], qa_percent_of_developer_hours: values[2] / 100, product_owner_percent_of_developer_hours: values[3] / 100, is_active: true, notes: form.notes || null };
    try {
      const existing = profiles.find((profile) => profile.jira_team.trim().toLowerCase() === payload.jira_team.toLowerCase());
      if (existing) await api.updateJiraTeamEstimationProfile(existing.id, payload); else await api.createJiraTeamEstimationProfile(payload);
      await onChanged();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save Jira Team profile"); } finally { setWorking(false); }
  }
  return <Card>
    <CardHeader><CardTitle>Jira Team Ticket Cost Profiles</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <p className="text-sm text-muted-foreground">Used only for ticket estimates. This is independent from SPARC Team rosters and does not change Forecast entry.</p>
      {profiles.length ? <div className="overflow-x-auto rounded border"><Table><TableHeader><TableRow><TableHead>Jira Team</TableHead><TableHead>Velocity</TableHead><TableHead>Dev Capacity</TableHead><TableHead>QA</TableHead><TableHead>PO</TableHead></TableRow></TableHeader><TableBody>{profiles.map((profile) => <TableRow key={profile.id}><TableCell className="font-semibold">{profile.jira_team}</TableCell><TableCell>{profile.velocity_story_points}</TableCell><TableCell>{profile.developer_capacity_hours} hrs</TableCell><TableCell>{profile.qa_percent_of_developer_hours * 100}%</TableCell><TableCell>{profile.product_owner_percent_of_developer_hours * 100}%</TableCell></TableRow>)}</TableBody></Table></div> : null}
      <div className="grid gap-3 md:grid-cols-3">
        <TextField label="Jira Team" value={form.jira_team} onChange={(jira_team) => setForm({ ...form, jira_team })} disabled={working} />
        <TextField label="Velocity (story points)" value={form.velocity_story_points} onChange={(velocity_story_points) => setForm({ ...form, velocity_story_points })} disabled={working} inputMode="decimal" />
        <TextField label="Developer capacity (hours)" value={form.developer_capacity_hours} onChange={(developer_capacity_hours) => setForm({ ...form, developer_capacity_hours })} disabled={working} inputMode="decimal" />
        <TextField label="QA % of Developer hours" value={form.qa_percent} onChange={(qa_percent) => setForm({ ...form, qa_percent })} disabled={working} inputMode="decimal" />
        <TextField label="PO % of Developer hours" value={form.po_percent} onChange={(po_percent) => setForm({ ...form, po_percent })} disabled={working} inputMode="decimal" />
        <TextField label="Notes" value={form.notes} onChange={(notes) => setForm({ ...form, notes })} disabled={working} />
      </div>
      {error ? <div className="text-sm text-destructive">{error}</div> : null}
      <Button onClick={() => void save()} disabled={working}>{working ? "Saving" : "Save Jira Team Profile"}</Button>
    </CardContent>
  </Card>;
}

function ProfileEditor({ form, onChange, disabled }: { form: ProfileForm; onChange: (form: ProfileForm) => void; disabled: boolean }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <TextField label="Name" value={form.name} onChange={(name) => onChange({ ...form, name })} disabled={disabled} />
        <TextField
          label="Monthly Capacity Hours"
          value={form.monthlyCapacityHours}
          onChange={(monthlyCapacityHours) => onChange({ ...form, monthlyCapacityHours })}
          disabled={disabled}
          inputMode="decimal"
        />
        <TextField
          label="Actual Completeness Threshold"
          value={form.actualCompletenessThreshold}
          onChange={(actualCompletenessThreshold) => onChange({ ...form, actualCompletenessThreshold })}
          disabled={disabled}
          inputMode="decimal"
        />
        <TextField
          label="Stale Ticket Window Days"
          value={form.staleTicketWindowDays}
          onChange={(staleTicketWindowDays) => onChange({ ...form, staleTicketWindowDays })}
          disabled={disabled}
          inputMode="numeric"
        />
        <TextField
          label="Future Average Window"
          value={form.futureMonthAverageWindow}
          onChange={(futureMonthAverageWindow) => onChange({ ...form, futureMonthAverageWindow })}
          disabled={disabled}
          inputMode="numeric"
        />
        <TextField
          label="Description"
          value={form.description}
          onChange={(description) => onChange({ ...form, description })}
          disabled={disabled}
        />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <CheckField
          label="Use forecast for future/planning months"
          checked={form.forecastFutureMonths}
          onChange={(forecastFutureMonths) => onChange({ ...form, forecastFutureMonths })}
          disabled={disabled}
        />
        <CheckField
          label="Use story points as optional weighting"
          checked={form.storyPointWeightingEnabled}
          onChange={(storyPointWeightingEnabled) => onChange({ ...form, storyPointWeightingEnabled })}
          disabled={disabled}
        />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <TextArea label="Excluded Statuses" value={form.excludedStatuses} onChange={(excludedStatuses) => onChange({ ...form, excludedStatuses })} disabled={disabled} />
        <TextArea label="Low Activity Statuses" value={form.lowActivityStatuses} onChange={(lowActivityStatuses) => onChange({ ...form, lowActivityStatuses })} disabled={disabled} />
        <TextArea label="Excluded Jira Project Keys" value={form.excludedJiraProjectKeys} onChange={(excludedJiraProjectKeys) => onChange({ ...form, excludedJiraProjectKeys })} disabled={disabled} />
        <TextArea label="Project Pause Dates JSON" value={form.projectPauseDates} onChange={(projectPauseDates) => onChange({ ...form, projectPauseDates })} disabled={disabled} />
        <TextArea label="Work Type Field Priority" value={form.workTypeFieldPriority} onChange={(workTypeFieldPriority) => onChange({ ...form, workTypeFieldPriority })} disabled={disabled} />
        <TextArea label="Notes" value={form.notes} onChange={(notes) => onChange({ ...form, notes })} disabled={disabled} />
      </div>
    </div>
  );
}

function PreviewCard({ preview }: { preview: EstimationPreview | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Preview Impact</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {preview ? (
          <>
            <div className="grid grid-cols-2 gap-2">
              <PreviewMetric label="Issues" value={String(preview.imported_issue_count)} />
              <PreviewMetric label="Included" value={String(preview.included_issue_count)} />
              <PreviewMetric label="Excluded" value={String(preview.excluded_issue_count)} />
              <PreviewMetric label="Unmapped" value={String(preview.unmapped_issue_count)} />
              <PreviewMetric label="Entries" value={String(preview.estimated_entry_count)} />
              <PreviewMetric label="Est. Hours" value={formatHours(preview.estimated_hours)} />
            </div>
            <div className="flex items-center gap-2">
              <Badge>{preview.status}</Badge>
              {preview.run_id ? <span className="text-sm text-muted-foreground">Run #{preview.run_id}</span> : null}
            </div>
            {preview.warnings.length ? (
              <div className="space-y-2">
                {preview.warnings.map((warning) => (
                  <div key={warning} className="flex gap-2 rounded-md border border-warning/40 bg-warning/10 p-2 text-sm">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                    <span>{warning}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Preview the profile before creating a new estimation run.</p>
        )}
      </CardContent>
    </Card>
  );
}

function RunHistory({ runs }: { runs: EstimationRun[] }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <History className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-lg font-semibold">Run History</h2>
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Method</TableHead>
                <TableHead>Issues</TableHead>
                <TableHead>Entries</TableHead>
                <TableHead>Warnings</TableHead>
                <TableHead>Completed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.length ? (
                runs.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>#{run.id}</TableCell>
                    <TableCell>
                      <Badge>{run.status}</Badge>
                    </TableCell>
                    <TableCell>{run.method_version}</TableCell>
                    <TableCell className="numeric-cell">{run.imported_issue_count}</TableCell>
                    <TableCell className="numeric-cell">{run.estimated_entry_count}</TableCell>
                    <TableCell className="numeric-cell">{run.warning_count}</TableCell>
                    <TableCell>{run.completed_at ? formatDateTime(run.completed_at) : "-"}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell className="py-5 text-muted-foreground" colSpan={7}>
                    No estimation runs yet.
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

function AllocationAudit({ rows }: { rows: EstimatedIssueAllocation[] }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Latest Run Audit Detail</h2>
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Issue</TableHead>
                <TableHead>Project</TableHead>
                <TableHead>Team Member</TableHead>
                <TableHead>Product</TableHead>
                <TableHead>Bucket</TableHead>
                <TableHead>Month</TableHead>
                <TableHead>Hours</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Reason</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length ? (
                rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <div className="font-medium">{row.issue_key}</div>
                      <div className="max-w-72 truncate text-xs text-muted-foreground">{row.issue_summary}</div>
                    </TableCell>
                    <TableCell>{row.jira_project_key}</TableCell>
                    <TableCell>
                      <TeamMemberNameLink className="font-medium" linkClassName="text-primary hover:underline" member={row}>
                        {row.team_member}
                      </TeamMemberNameLink>
                    </TableCell>
                    <TableCell>{row.product ?? "-"}</TableCell>
                    <TableCell>{row.bucket ?? "-"}</TableCell>
                    <TableCell>{row.month_label ?? "-"}</TableCell>
                    <TableCell className="numeric-cell">{formatHours(row.allocated_hours)}</TableCell>
                    <TableCell>
                      <Badge className={row.included ? "border-primary/40 text-primary" : "border-warning/40 text-warning"}>
                        {row.included ? "Included" : "Excluded"}
                      </Badge>
                    </TableCell>
                    <TableCell className="min-w-64 text-muted-foreground">{row.inclusion_reason ?? row.exclusion_reason ?? "-"}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell className="py-5 text-muted-foreground" colSpan={9}>
                    No audit rows available yet.
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

function TextField({
  label,
  value,
  onChange,
  disabled,
  inputMode,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  inputMode?: "decimal" | "numeric";
}) {
  return (
    <label className="space-y-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <Input disabled={disabled} inputMode={inputMode} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function TextArea({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  return (
    <label className="space-y-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <textarea
        className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        disabled={disabled}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function CheckField({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled: boolean;
}) {
  return (
    <label className="flex items-center gap-3 rounded-md border bg-secondary/50 px-3 py-2 text-sm">
      <input checked={checked} disabled={disabled} type="checkbox" onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function Guardrail({ text }: { text: string }) {
  return (
    <div className="flex gap-2">
      <span className="mt-1 h-2 w-2 rounded-full bg-primary" />
      <span>{text}</span>
    </div>
  );
}

function PreviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-secondary px-3 py-2">
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <div className="numeric-cell text-right text-lg font-semibold text-primary">{value}</div>
    </div>
  );
}

function formFromProfile(profile: EstimationProfile): ProfileForm {
  return {
    name: profile.name,
    description: profile.description ?? "",
    monthlyCapacityHours: String(profile.monthly_capacity_hours),
    actualCompletenessThreshold: String(profile.actual_completeness_threshold),
    staleTicketWindowDays: String(profile.stale_ticket_window_days),
    forecastFutureMonths: profile.forecast_future_months,
    futureMonthAverageWindow: String(profile.future_month_average_window),
    excludedStatuses: profile.excluded_statuses ?? "",
    lowActivityStatuses: profile.low_activity_statuses ?? "",
    excludedJiraProjectKeys: profile.excluded_jira_project_keys ?? "",
    projectPauseDates: profile.project_pause_dates ?? "",
    workTypeFieldPriority: profile.work_type_field_priority ?? "",
    storyPointWeightingEnabled: profile.story_point_weighting_enabled,
    notes: profile.notes ?? "",
  };
}

function profilePayload(form: ProfileForm) {
  const monthlyCapacityHours = Number(form.monthlyCapacityHours);
  const actualCompletenessThreshold = Number(form.actualCompletenessThreshold);
  const staleTicketWindowDays = Number(form.staleTicketWindowDays);
  const futureMonthAverageWindow = Number(form.futureMonthAverageWindow);
  if (
    !Number.isFinite(monthlyCapacityHours) ||
    !Number.isFinite(actualCompletenessThreshold) ||
    !Number.isFinite(staleTicketWindowDays) ||
    !Number.isFinite(futureMonthAverageWindow)
  ) {
    return null;
  }
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    monthly_capacity_hours: monthlyCapacityHours,
    actual_completeness_threshold: actualCompletenessThreshold,
    stale_ticket_window_days: Math.max(1, Math.round(staleTicketWindowDays)),
    forecast_future_months: form.forecastFutureMonths,
    future_month_average_window: Math.max(1, Math.round(futureMonthAverageWindow)),
    excluded_statuses: form.excludedStatuses.trim() || null,
    low_activity_statuses: form.lowActivityStatuses.trim() || null,
    excluded_jira_project_keys: form.excludedJiraProjectKeys.trim() || null,
    project_pause_dates: form.projectPauseDates.trim() || null,
    work_type_field_priority: form.workTypeFieldPriority.trim() || null,
    story_point_weighting_enabled: form.storyPointWeightingEnabled,
    notes: form.notes.trim() || null,
  };
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
