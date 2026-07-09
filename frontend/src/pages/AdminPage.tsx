import { DatabaseZap, FileSpreadsheet, Terminal, UserCog, Users, type LucideIcon } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { PageNav } from "../components/PageNav";
import { Button } from "../components/ui/button";
import { AdminDataPage } from "./AdminDataPage";
import { AdminTeamRosterPage } from "./AdminTeamRosterPage";
import { IntegrationsPage } from "./IntegrationsPage";
import { SystemScanPage } from "./SystemScanPage";
import { AdminUsersPage } from "./AdminUsersPage";

type AdminTab = "jira" | "roster" | "users" | "data" | "scan";

const tabs: Array<{ key: AdminTab; label: string; href: string; icon: LucideIcon }> = [
  { key: "jira", label: "Jira", href: "/admin?tab=jira", icon: DatabaseZap },
  { key: "roster", label: "Team Roster", href: "/admin?tab=roster", icon: Users },
  { key: "users", label: "Users", href: "/admin?tab=users", icon: UserCog },
  { key: "scan", label: "System Scan", href: "/admin?tab=scan", icon: Terminal },
  { key: "data", label: "Admin Data", href: "/admin?tab=data", icon: FileSpreadsheet },
];

export function AdminPage() {
  const [searchParams] = useSearchParams();
  const activeTab = adminTabFromParam(searchParams.get("tab"));

  return (
    <div className="space-y-5">
      <section className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold">Admin</h1>
          <p className="mt-1 text-sm text-muted-foreground">Manage Jira sync operations and SPARC-owned admin data movement.</p>
        </div>
        <PageNav current="admin" />
      </section>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Admin sections">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const selected = tab.key === activeTab;
          return (
            <Button asChild key={tab.key} variant={selected ? "default" : "outline"}>
              <Link aria-selected={selected} role="tab" to={tab.href}>
                <Icon className="h-4 w-4" />
                {tab.label}
              </Link>
            </Button>
          );
        })}
      </div>

      <div role="tabpanel">
        {activeTab === "jira" ? (
          <IntegrationsPage embedded />
        ) : activeTab === "roster" ? (
          <AdminTeamRosterPage embedded />
        ) : activeTab === "users" ? (
          <AdminUsersPage />
        ) : activeTab === "scan" ? (
          <SystemScanPage embedded />
        ) : (
          <AdminDataPage embedded />
        )}
      </div>
    </div>
  );
}

function adminTabFromParam(value: string | null): AdminTab {
  if (value === "data" || value === "roster" || value === "scan" || value === "users") return value;
  return "jira";
}
