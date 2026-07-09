import { formatCurrency } from "./utils";

const fteEmploymentTypes = new Set(["employee", "fte", "full time", "full-time", "fulltime"]);
const vendorEmploymentTypes = new Set(["vendor"]);
const contractorEmploymentTypes = new Set(["contractor", "contract"]);

export function isFteEmploymentType(value: string) {
  return fteEmploymentTypes.has(normalizeEmploymentType(value));
}

export function isVendorEmploymentType(value: string) {
  return vendorEmploymentTypes.has(normalizeEmploymentType(value));
}

export function isContractorEmploymentType(value: string) {
  return contractorEmploymentTypes.has(normalizeEmploymentType(value));
}

export function formatBillRate(billRate: number | null | undefined, employmentType: string, options?: { includeUnit?: boolean }) {
  if (billRate == null) return "Hidden";
  if (isFteEmploymentType(employmentType) && billRate <= 0) return "Not set";
  return `${formatCurrency(billRate)}${options?.includeUnit ? "/hr" : ""}`;
}

function normalizeEmploymentType(value: string) {
  return value.replace(/_/g, " ").trim().toLowerCase().replace(/\s+/g, " ");
}
