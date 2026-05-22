import { DatabaseZap, FileSpreadsheet, LayoutDashboard, Package, Users, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "./ui/button";

type PageNavKey = "dashboard" | "products" | "team" | "jira" | "admin-data";

const navLinks: Array<{ key: PageNavKey; label: string; href: string; icon: LucideIcon }> = [
  { key: "dashboard", label: "Dashboard", href: "/", icon: LayoutDashboard },
  { key: "products", label: "Products", href: "/products/settings", icon: Package },
  { key: "team", label: "Team", href: "/team", icon: Users },
  { key: "jira", label: "Jira Sync", href: "/integrations", icon: DatabaseZap },
  { key: "admin-data", label: "Admin Data", href: "/admin-data", icon: FileSpreadsheet },
];

export function PageNav({ current }: { current?: PageNavKey }) {
  return (
    <nav aria-label="Page navigation" className="flex flex-wrap justify-end gap-2">
      {navLinks
        .filter((link) => link.key !== current)
        .map((link) => {
          const Icon = link.icon;
          return (
            <Button asChild key={link.key} variant="outline">
              <Link to={link.href}>
                <Icon className="h-4 w-4" />
                {link.label}
              </Link>
            </Button>
          );
        })}
    </nav>
  );
}
