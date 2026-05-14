import type { PropsWithChildren } from "react";
import { Link, NavLink } from "react-router-dom";

export function Layout({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div
          aria-hidden="true"
          className="h-1"
          style={{
            background:
              "linear-gradient(90deg, var(--spark-red) 0 33.33%, var(--spark-navy) 33.33% 66.66%, var(--spark-gray) 66.66% 100%)",
          }}
        />
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-baseline gap-3 text-primary">
            <span className="text-lg font-semibold">SPARK</span>
            <span className="hidden text-sm text-muted-foreground sm:inline">Staff Planning & Resource Knowledge</span>
          </Link>
          <NavLink
            to="/"
            className={({ isActive }) =>
              `rounded-md px-3 py-2 text-sm font-medium ${isActive ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"}`
            }
          >
            Dashboard
          </NavLink>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
    </div>
  );
}
