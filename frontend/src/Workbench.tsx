import { useState } from "react";

import { App } from "./App";
import { ApplicationDashboard } from "./ApplicationDashboard";
import { MarketIntelligence } from "./MarketIntelligence";
import { ProfessionalIntelligence } from "./ProfessionalIntelligence";
import "./Workbench.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
type WorkbenchView = "opportunities" | "applications" | "market" | "professional";

const VIEWS: Array<{ id: WorkbenchView; label: string; description: string }> = [
  { id: "opportunities", label: "Opportunities", description: "Review, prioritise, and prepare opportunities." },
  { id: "applications", label: "Applications", description: "Track active applications and outcomes." },
  { id: "market", label: "Market", description: "Turn captured jobs into role, skill, location, and fit intelligence." },
  { id: "professional", label: "Professional", description: "Review approved professional sources and supervised evidence boundaries." },
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

      <div className="workspace-view-stack">
        <div className="workspace-view workspace-view-opportunities" hidden={activeView !== "opportunities"}>
          <App />
        </div>
        <div className="workspace-view workspace-view-applications" hidden={activeView !== "applications"}>
          <ApplicationDashboard apiBase={API_BASE} active={activeView === "applications"} />
        </div>
        <div className="workspace-view workspace-view-market" hidden={activeView !== "market"}>
          <MarketIntelligence apiBase={API_BASE} />
        </div>
        <div className="workspace-view workspace-view-professional" hidden={activeView !== "professional"}>
          <ProfessionalIntelligence apiBase={API_BASE} active={activeView === "professional"} />
        </div>
      </div>
    </div>
  );
}
