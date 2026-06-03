export const appConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
  buildVersion: import.meta.env.VITE_BUILD_VERSION ?? "local",
  fiscalYear: Number(import.meta.env.VITE_DEFAULT_FISCAL_YEAR ?? 2027),
};
