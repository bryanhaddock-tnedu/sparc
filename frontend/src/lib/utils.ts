import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatHours(value: number | null | undefined) {
  return `${Number(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}`;
}

export function formatCurrency(value: number | null | undefined) {
  return Number(value ?? 0).toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}
