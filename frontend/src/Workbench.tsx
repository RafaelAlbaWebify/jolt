import { useState } from "react";

import { App } from "./App";
import { ApplicationDashboard } from "./ApplicationDashboard";
import { IdentityEvidenceDashboard } from "./IdentityEvidenceDashboard";
import "./Workbench.css";

type WorkbenchView = "opportunities" | "applications" | "evidence";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const VIEWS: Array<{
  id: WorkbenchView;
  label: string;
  description: string;
}> = [
  {
    id: "opportunities",
    label: "Opportunities",
    description: "Review, prioritise, and prepare opportunities.",
  },
  {
    id: "applications",
    label: "Applications",
    description: "Track active applications and outcomes.",
  },
  {
    id: "evidence",
    label: "Evidence",
    description: "Inspect identity and operational evidence.",
  },
];

export function Workbench() {
  const [activeView, setActiveView] = useState<WorkbenchView>("opportunities");
  const view = VIEWS.find((item) => item.id === activeView) ?? VIEWS[0];

  return (
    <div className="shell workspace-shell">
      <header className="workspace-header">
        <div className="hero">
          <p className="eyebrow">Job Opportunity Learning & Tracking</p>
          <h1>JOLT</h1>
          <p>Turn job evidence into an auditable decision, application workflow, and outcome history.</p>
        </div>

        <nav className="workspace-nav" aria-label="JOLT workspace views">
          {VIEWS.map((item) => (
            <button
              type="button"
              className={activeView === item.id ? "workspace-nav-active" : "secondary"}
              aria-pressed={activeView === item.id}
              onClick={() => setActiveView(item.id)}
              key={item.id}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <p className="workspace-description">{view.description}</p>
      </header>

      <div className={`workspace-view workspace-view-${activeView}`} aria-live="polite">
        {activeView === "opportunities" && <App />}
        {activeView === "applications" && <ApplicationDashboard apiBase={API_BASE} />}
        {activeView === "evidence" && <IdentityEvidenceDashboard apiBase={API_BASE} />}
      </div>
    </div>
  );
}
