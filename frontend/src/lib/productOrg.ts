export const OFFICE_OPTIONS = ["Academics", "Operations", "Programs", "Deputy Commissioner", "Commissioners Office", "General Counsel"] as const;

export type ProductOffice = (typeof OFFICE_OPTIONS)[number];

export const DIVISION_OPTIONS_BY_OFFICE: Record<ProductOffice, string[]> = {
  Academics: [
    "Academics & Instruction",
    "Post-secondary, Workforce, CTE, & Military Readiness",
    "Centers of Regional Excellence (CORE)",
    "Early Learning",
    "Human Capital",
    "Special Education & Student Supports",
  ],
  Operations: ["Finance", "IT", "Coordinated School Health"],
  Programs: [
    "Assessment, Accountability & Research",
    "School Choice",
    "Federal Programs & Oversight",
    "School Turnaround",
    "State Special Schools",
  ],
  "Deputy Commissioner": ["Operational Data Strategy", "Performance Management"],
  "Commissioners Office": ["Communications", "Policy & Legislative Affairs"],
  "General Counsel": [],
};

export function isProductOffice(value: string | null | undefined): value is ProductOffice {
  return OFFICE_OPTIONS.includes(value as ProductOffice);
}

export function divisionOptionsForOffice(office: string | null | undefined): string[] {
  return isProductOffice(office) ? DIVISION_OPTIONS_BY_OFFICE[office] : [];
}

export function divisionBelongsToOffice(office: string | null | undefined, division: string | null | undefined): boolean {
  if (!division) return true;
  return divisionOptionsForOffice(office).includes(division);
}
