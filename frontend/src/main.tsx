import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { ApplicationDashboard } from "./ApplicationDashboard";
import { IdentityEvidenceDashboard } from "./IdentityEvidenceDashboard";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element was not found.");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
    <main className="shell">
      <ApplicationDashboard apiBase={API_BASE} />
      <IdentityEvidenceDashboard apiBase={API_BASE} />
    </main>
  </StrictMode>,
);
