import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./index.css";
import { appConfig } from "./lib/config";

const ACTIVE_BUILD_VERSION = appConfig.buildVersion;
const MAX_BUILD_RELOAD_ATTEMPTS = 3;

document.documentElement.dataset.sparcBuildVersion = ACTIVE_BUILD_VERSION;

void reloadForNewBuild();

async function reloadForNewBuild() {
  if (import.meta.env.DEV || ACTIVE_BUILD_VERSION === "local") return;

  try {
    const params = new URLSearchParams({ current: ACTIVE_BUILD_VERSION, t: String(Date.now()) });
    const response = await fetch(`${appConfig.apiBaseUrl}/api/app-version?${params.toString()}`, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) return;

    const payload = (await response.json()) as { version?: string };
    const deployedVersion = payload.version;
    if (!deployedVersion || deployedVersion === "local" || deployedVersion === ACTIVE_BUILD_VERSION) return;

    const reloadKey = `sparc:build-reload:${ACTIVE_BUILD_VERSION}->${deployedVersion}`;
    const reloadAttempts = Number.parseInt(window.sessionStorage.getItem(reloadKey) ?? "0", 10) || 0;
    if (reloadAttempts >= MAX_BUILD_RELOAD_ATTEMPTS) return;
    window.sessionStorage.setItem(reloadKey, String(reloadAttempts + 1));

    const url = new URL(window.location.href);
    url.searchParams.set("sparcBuild", deployedVersion.slice(0, 12));
    url.searchParams.set("sparcReload", String(Date.now()));
    window.location.replace(url.toString());
  } catch {
    // Version checks should never block app startup.
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
