import { BarChart3, Settings, LayoutDashboard, Package, Users, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../lib/auth";
import { Button } from "./ui/button";

type PageNavKey = "dashboard" | "products" | "team" | "reports" | "admin";

const navLinks: Array<{ key: PageNavKey; label: string; href: string; icon: LucideIcon; iconOnly?: boolean }> = [
  { key: "dashboard", label: "Dashboard", href: "/", icon: LayoutDashboard },
  { key: "products", label: "Products", href: "/products/settings", icon: Package },
  { key: "team", label: "Team", href: "/team", icon: Users },
  { key: "reports", label: "Reports", href: "/reports", icon: BarChart3 },
  { key: "admin", label: "Admin", href: "/admin", icon: Settings, iconOnly: true },
];

export function PageNav({ current }: { current?: PageNavKey }) {
  const { status } = useAuth();
  const canAdmin = status?.capabilities.can_admin === true;
  const canViewNamedPeople = status?.capabilities.can_view_named_people === true;
  const canViewReports = status?.capabilities.can_view_reports === true;

  return (
    <nav aria-label="Page navigation" className="flex flex-nowrap justify-end gap-2">
      {navLinks
        .filter(
          (link) =>
            link.key !== current &&
            (link.key !== "admin" || canAdmin) &&
            (link.key !== "team" || canViewNamedPeople) &&
            (link.key !== "reports" || canViewReports),
        )
        .map((link) => {
          const Icon = link.icon;
          if (link.iconOnly) {
            return (
              <Button asChild key={link.key} size="icon" variant="outline">
                <Link aria-label={link.label} title={link.label} to={link.href}>
                  <Icon className="h-4 w-4" />
                  <span className="sr-only">{link.label}</span>
                </Link>
              </Button>
            );
          }
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
