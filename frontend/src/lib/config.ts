import packageMetadata from "../../package.json";

const envBuildVersion = import.meta.env.VITE_BUILD_VERSION;

export const appConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
  buildVersion: envBuildVersion && envBuildVersion !== "local" ? envBuildVersion : packageMetadata.version,
  fiscalYear: Number(import.meta.env.VITE_DEFAULT_FISCAL_YEAR ?? 2027),
};
