import { useEffect, useMemo, useState } from "react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { api } from "../lib/api";
import { OFFICE_OPTIONS } from "../lib/productOrg";
import type { AccessRole, AppUser, AppUserCreatePayload, AppUserUpdatePayload } from "../types/api";

type UserDraft = {
  email: string;
  display_name: string;
  role: AccessRole;
  program_areas: string[];
  active: boolean;
  local_login_enabled: boolean;
  temporary_password: string;
};

const ROLE_OPTIONS: Array<{ value: AccessRole; label: string }> = [
  { value: "ADMIN", label: "Admin" },
  { value: "LEADERSHIP_VIEW_ONLY", label: "Leadership View Only" },
  { value: "PROGRAM_AREA_VIEW_ONLY", label: "Program Area View Only" },
];

const EMPTY_CREATE_DRAFT: UserDraft = {
  email: "",
  display_name: "",
  role: "PROGRAM_AREA_VIEW_ONLY",
  program_areas: [],
  active: true,
  local_login_enabled: true,
  temporary_password: "",
};

export function AdminUsersPage() {
  const [users, setUsers] = useState<AppUser[]>([]);
  const [drafts, setDrafts] = useState<Record<number, UserDraft>>({});
  const [newUser, setNewUser] = useState<UserDraft>(EMPTY_CREATE_DRAFT);
  const [loading, setLoading] = useState(true);
  const [savingUserId, setSavingUserId] = useState<number | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    loadUsers();
  }, []);

  const sortedUsers = useMemo(
    () => [...users].sort((left, right) => left.display_name.localeCompare(right.display_name) || left.email.localeCompare(right.email)),
    [users],
  );

  async function loadUsers() {
    setLoading(true);
    setError(null);
    try {
      const loadedUsers = await api.adminUsers();
      setUsers(loadedUsers);
      setDrafts(Object.fromEntries(loadedUsers.map((user) => [user.id, draftFromUser(user)])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load users");
    } finally {
      setLoading(false);
    }
  }

  async function createUser() {
    setSavingUserId("new");
    setError(null);
    setMessage(null);
    try {
      const payload: AppUserCreatePayload = {
        email: newUser.email,
        display_name: newUser.display_name,
        role: newUser.role,
        program_areas: newUser.program_areas,
        active: newUser.active,
        local_login_enabled: newUser.local_login_enabled,
        temporary_password: newUser.temporary_password || null,
      };
      const created = await api.createAdminUser(payload);
      setUsers((current) => [...current, created]);
      setDrafts((current) => ({ ...current, [created.id]: draftFromUser(created) }));
      setNewUser(EMPTY_CREATE_DRAFT);
      setMessage(`${created.display_name} created`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create user");
    } finally {
      setSavingUserId(null);
    }
  }

  async function saveUser(user: AppUser) {
    const draft = drafts[user.id];
    if (!draft) return;
    setSavingUserId(user.id);
    setError(null);
    setMessage(null);
    try {
      const payload: AppUserUpdatePayload = {
        email: draft.email,
        display_name: draft.display_name,
        role: draft.role,
        program_areas: draft.program_areas,
        active: draft.active,
        local_login_enabled: draft.local_login_enabled,
        temporary_password: draft.temporary_password || null,
      };
      const updated = await api.updateAdminUser(user.id, payload);
      setUsers((current) => current.map((candidate) => (candidate.id === updated.id ? updated : candidate)));
      setDrafts((current) => ({ ...current, [updated.id]: draftFromUser(updated) }));
      setMessage(`${updated.display_name} updated`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update user");
    } finally {
      setSavingUserId(null);
    }
  }

  function updateDraft(userId: number, updates: Partial<UserDraft>) {
    setMessage(null);
    setDrafts((current) => ({ ...current, [userId]: { ...current[userId], ...updates } }));
  }

  return (
    <div className="space-y-5">
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}
      {message ? <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700">{message}</div> : null}

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Create User</h2>
        </div>
        <div className="grid gap-3 lg:grid-cols-[minmax(12rem,1fr)_minmax(12rem,1fr)_13rem_minmax(14rem,1.2fr)_12rem_auto] lg:items-start">
          <Input aria-label="New user email" placeholder="email@tnedu.gov" value={newUser.email} onChange={(event) => setNewUser({ ...newUser, email: event.target.value })} />
          <Input
            aria-label="New user display name"
            placeholder="Display name"
            value={newUser.display_name}
            onChange={(event) => setNewUser({ ...newUser, display_name: event.target.value })}
          />
          <RoleSelect value={newUser.role} onChange={(role) => setNewUser({ ...newUser, role })} />
          <ProgramAreaPicker value={newUser.program_areas} onChange={(program_areas) => setNewUser({ ...newUser, program_areas })} />
          <Input
            aria-label="New user temporary password"
            placeholder="Temporary password"
            type="password"
            value={newUser.temporary_password}
            onChange={(event) => setNewUser({ ...newUser, temporary_password: event.target.value })}
          />
          <Button disabled={savingUserId === "new" || !newUser.email || !newUser.display_name} onClick={createUser}>
            Create
          </Button>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Users</h2>
            <p className="mt-1 text-sm text-muted-foreground">Change a row, then use Save changes on the right to apply role or Program Area updates.</p>
          </div>
          <Button variant="outline" onClick={loadUsers} disabled={loading}>
            Refresh
          </Button>
        </div>
        <div className="overflow-x-auto rounded-md border">
          <Table className="min-w-[84rem]">
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Program Areas</TableHead>
                <TableHead>Access</TableHead>
                <TableHead>Temporary Password</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-muted-foreground">
                    Loading users...
                  </TableCell>
                </TableRow>
              ) : sortedUsers.length ? (
                sortedUsers.map((user) => {
                  const draft = drafts[user.id] ?? draftFromUser(user);
                  const dirty = hasDraftChanges(user, draft);
                  return (
                    <TableRow key={user.id}>
                      <TableCell className="min-w-[16rem]">
                        <div className="space-y-2">
                          <Input
                            aria-label={`${user.email} display name`}
                            value={draft.display_name}
                            onChange={(event) => updateDraft(user.id, { display_name: event.target.value })}
                          />
                          <Input aria-label={`${user.email} email`} value={draft.email} onChange={(event) => updateDraft(user.id, { email: event.target.value })} />
                          <div className="flex flex-wrap gap-1">
                            {user.sso_linked ? <Badge>SSO linked</Badge> : <Badge className="bg-muted text-muted-foreground">SSO pending</Badge>}
                            {user.has_local_password ? <Badge className="bg-muted text-muted-foreground">Local password</Badge> : null}
                            {dirty ? <Badge className="border-amber-400 bg-amber-100 text-amber-800">Unsaved changes</Badge> : null}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="min-w-[13rem]">
                        <RoleSelect value={draft.role} onChange={(role) => updateDraft(user.id, { role })} />
                      </TableCell>
                      <TableCell className="min-w-[16rem]">
                        <ProgramAreaPicker value={draft.program_areas} onChange={(program_areas) => updateDraft(user.id, { program_areas })} />
                      </TableCell>
                      <TableCell className="min-w-[10rem]">
                        <label className="flex items-center gap-2 text-sm">
                          <input checked={draft.active} type="checkbox" onChange={(event) => updateDraft(user.id, { active: event.target.checked })} />
                          Active
                        </label>
                        <label className="mt-2 flex items-center gap-2 text-sm">
                          <input
                            checked={draft.local_login_enabled}
                            type="checkbox"
                            onChange={(event) => updateDraft(user.id, { local_login_enabled: event.target.checked })}
                          />
                          Local login
                        </label>
                      </TableCell>
                      <TableCell className="min-w-[11rem]">
                        <Input
                          aria-label={`${user.email} temporary password`}
                          placeholder="Leave unchanged"
                          type="password"
                          value={draft.temporary_password}
                          onChange={(event) => updateDraft(user.id, { temporary_password: event.target.value })}
                        />
                      </TableCell>
                      <TableCell className="text-right">
                        <Button disabled={savingUserId === user.id || !dirty} onClick={() => saveUser(user)}>
                          {savingUserId === user.id ? "Saving" : dirty ? "Save changes" : "Saved"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-muted-foreground">
                    No users
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}

function RoleSelect({ value, onChange }: { value: AccessRole; onChange: (value: AccessRole) => void }) {
  return (
    <select
      aria-label="Role"
      className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
      value={value}
      onChange={(event) => onChange(event.target.value as AccessRole)}
    >
      {ROLE_OPTIONS.map((role) => (
        <option key={role.value} value={role.value}>
          {role.label}
        </option>
      ))}
    </select>
  );
}

function ProgramAreaPicker({ value, onChange }: { value: string[]; onChange: (value: string[]) => void }) {
  function toggle(programArea: string, selected: boolean) {
    if (selected) {
      onChange([...value, programArea].filter((item, index, array) => array.indexOf(item) === index));
      return;
    }
    onChange(value.filter((item) => item !== programArea));
  }

  return (
    <div className="grid gap-1">
      {OFFICE_OPTIONS.map((programArea) => (
        <label key={programArea} className="flex items-center gap-2 text-sm">
          <input checked={value.includes(programArea)} type="checkbox" onChange={(event) => toggle(programArea, event.target.checked)} />
          {programArea}
        </label>
      ))}
    </div>
  );
}

function draftFromUser(user: AppUser): UserDraft {
  return {
    email: user.email,
    display_name: user.display_name,
    role: user.role,
    program_areas: user.program_areas,
    active: user.active,
    local_login_enabled: user.local_login_enabled,
    temporary_password: "",
  };
}

function hasDraftChanges(user: AppUser, draft: UserDraft) {
  return (
    draft.email !== user.email ||
    draft.display_name !== user.display_name ||
    draft.role !== user.role ||
    draft.active !== user.active ||
    draft.local_login_enabled !== user.local_login_enabled ||
    draft.temporary_password.length > 0 ||
    !sameStringSet(draft.program_areas, user.program_areas)
  );
}

function sameStringSet(left: string[], right: string[]) {
  if (left.length !== right.length) return false;
  const normalizedRight = new Set(right);
  return left.every((value) => normalizedRight.has(value));
}
