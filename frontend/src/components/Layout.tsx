import type { PropsWithChildren } from "react";
import { Link } from "react-router-dom";

import tdoeLogo from "../assets/tdoe-logo.png";
import { useAuth } from "../lib/auth";
import { fiscalYearRangeLabel, useFiscalYear } from "../lib/fiscalYear";
import { Button } from "./ui/button";

export function Layout({ children }: PropsWithChildren) {
  const { fiscalYear, fiscalYearOptions, setFiscalYear } = useFiscalYear();
  const { status, logout } = useAuth();
  const currentYear = new Date().getFullYear();

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="border-b bg-card">
        <div
          aria-hidden="true"
          className="h-1"
          style={{
            background:
              "linear-gradient(90deg, var(--spark-red) 0 33.33%, var(--spark-navy) 33.33% 66.66%, var(--spark-gray) 66.66% 100%)",
          }}
        />
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <Link to="/" className="flex items-center gap-3 text-primary">
            <img src={tdoeLogo} alt="TDOE logo" className="h-9 w-auto shrink-0" />
            <span className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-3">
              <span className="text-lg font-semibold leading-none">SPARC</span>
              <span className="hidden text-sm text-muted-foreground sm:inline">Staff planning and resource intelligence</span>
            </span>
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor="fiscal-year-selector">
              Fiscal year
            </label>
            <select
              id="fiscal-year-selector"
              className="h-9 rounded-md border border-input bg-background px-3 text-sm font-medium text-foreground"
              value={fiscalYear}
              onChange={(event) => setFiscalYear(Number(event.target.value))}
            >
              {fiscalYearOptions.map((option) => (
                <option key={option} value={option}>
                  FY{option} ({fiscalYearRangeLabel(option)})
                </option>
              ))}
            </select>
            {status?.auth_enabled ? (
              <Button type="button" variant="outline" onClick={() => void logout()}>
                Sign out
              </Button>
            ) : null}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      <footer className="mx-auto w-full max-w-7xl px-4 pb-8 pt-10 text-xs text-muted-foreground sm:px-6 lg:px-8">
        <div className="border-t pt-4">Copyright {currentYear} Tennessee Department of Education. All rights reserved.</div>
      </footer>
    </div>
  );
}
