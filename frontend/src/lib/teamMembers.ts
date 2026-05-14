import { formatCurrency } from "./utils";

const fteEmploymentTypes = new Set(["employee", "fte", "full time", "full-time", "fulltime"]);

export function isFteEmploymentType(value: string) {
  return fteEmploymentTypes.has(value.replace(/_/g, " ").trim().toLowerCase().replace(/\s+/g, " "));
}

export function formatBillRate(billRate: number, employmentType: string, options?: { includeUnit?: boolean }) {
  if (isFteEmploymentType(employmentType) && billRate <= 0) return "Not set";
  return `${formatCurrency(billRate)}${options?.includeUnit ? "/hr" : ""}`;
}
